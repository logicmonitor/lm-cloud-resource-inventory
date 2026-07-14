"""Tests for the LicenseCalculator class."""

import json
import math
import os
import tempfile

import pytest

from src.calculator.license_calculator import LicenseCalculator


@pytest.fixture
def sample_mappings():
    return {
        "aws": {
            "ec2:instance": {"category": "IaaS", "unit": "Instance"},
            "lambda:function": {"category": "PaaS", "unit": "Function"},
            "s3:bucket": {"category": "Non-Compute", "unit": "Bucket"},
        },
        "azure": {
            "microsoft.compute/virtualmachines": {"category": "IaaS", "unit": "VM"},
        },
    }


@pytest.fixture
def sample_rules():
    return {
        "no_charge_resources": {
            "aws": ["iam:*", "cloudformation:stack"],
            "azure": ["microsoft.resources/subscriptions"],
        }
    }


@pytest.fixture
def calculator(sample_mappings, sample_rules):
    return LicenseCalculator(
        resource_mappings=sample_mappings,
        license_rules=sample_rules,
    )


@pytest.fixture
def sample_inventory():
    return [
        {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "us-east-1",
            "resource_type": "ec2:instance",
            "count": 10,
        },
        {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "us-east-1",
            "resource_type": "lambda:function",
            "count": 21,
        },
        {
            "provider": "aws",
            "account_id": "123456789012",
            "region": "us-east-1",
            "resource_type": "s3:bucket",
            "count": 5,
        },
        {
            "provider": "azure",
            "account_id": "sub-1",
            "region": "eastus",
            "resource_type": "microsoft.compute/virtualmachines",
            "count": 3,
        },
    ]


# --- Pattern matching ---

class TestMatchesPattern:
    def test_exact_match(self, calculator):
        assert calculator._matches_pattern("ec2:instance", "ec2:instance")

    def test_no_match(self, calculator):
        assert not calculator._matches_pattern("ec2:instance", "lambda:function")

    def test_wildcard_suffix(self, calculator):
        assert calculator._matches_pattern("iam:role", "iam:*")

    def test_wildcard_prefix(self, calculator):
        assert calculator._matches_pattern("something.storage", "*.storage")

    def test_wildcard_middle(self, calculator):
        assert calculator._matches_pattern("microsoft.compute/vms", "microsoft.*/vms")

    def test_case_insensitive(self, calculator):
        assert calculator._matches_pattern("IAM:Role", "iam:*")
        assert calculator._matches_pattern("iam:role", "IAM:*")

    def test_question_mark_wildcard(self, calculator):
        assert calculator._matches_pattern("ec2:x", "ec2:?")
        assert not calculator._matches_pattern("ec2:xy", "ec2:?")


# --- Category lookups ---

class TestGetCategory:
    def test_exact_match(self, calculator):
        assert calculator.get_category("aws", "ec2:instance") == "IaaS"

    def test_case_insensitive_match(self, calculator):
        assert calculator.get_category("aws", "EC2:Instance") == "IaaS"

    def test_no_charge_exact(self, calculator):
        assert calculator.get_category("aws", "cloudformation:stack") == "No-Charge"

    def test_no_charge_wildcard(self, calculator):
        assert calculator.get_category("aws", "iam:role") == "No-Charge"
        assert calculator.get_category("aws", "iam:policy") == "No-Charge"

    def test_unsupported_type(self, calculator):
        assert calculator.get_category("aws", "unknown:thing") == "Unsupported"
        assert ("aws", "unknown:thing") in calculator.get_unsupported_types()

    def test_unknown_provider(self, calculator):
        assert calculator.get_category("gcp", "some.type") == "Unsupported"

    def test_unsupported_types_reset_on_calculate(self, calculator, sample_inventory):
        calculator.get_category("aws", "fake:type")
        assert len(calculator.get_unsupported_types()) == 1
        calculator.calculate(sample_inventory)
        assert ("aws", "fake:type") not in calculator.get_unsupported_types()


# --- HRU calculation ---

class TestHybridResourceUnits:
    def test_iaas_only(self, calculator):
        assert calculator.calculate_hybrid_units(10, 0) == 10

    def test_paas_only_exact(self, calculator):
        assert calculator.calculate_hybrid_units(0, 7) == 1

    def test_paas_rounds_up(self, calculator):
        assert calculator.calculate_hybrid_units(0, 8) == 2
        assert calculator.calculate_hybrid_units(0, 1) == 1

    def test_combined(self, calculator):
        assert calculator.calculate_hybrid_units(10, 14) == 12

    def test_zero(self, calculator):
        assert calculator.calculate_hybrid_units(0, 0) == 0


# --- Full calculate ---

class TestCalculate:
    def test_basic_calculation(self, calculator, sample_inventory):
        results = calculator.calculate(sample_inventory)

        totals = results["summary"]["totals"]
        assert totals["IaaS"] == 13
        assert totals["PaaS"] == 21
        assert totals["Non-Compute"] == 5

        assert results["summary"]["hybrid_units"] == 13 + math.ceil(21 / 7)

    def test_by_provider_are_plain_dicts(self, calculator, sample_inventory):
        results = calculator.calculate(sample_inventory)
        by_provider = results["summary"]["by_provider"]

        for _provider, cats in by_provider.items():
            assert type(cats) is dict

    def test_empty_inventory(self, calculator):
        results = calculator.calculate([])
        assert results["summary"]["totals"] == {}
        assert results["summary"]["hybrid_units"] == 0
        assert results["detailed"] == []

    def test_unsupported_types_not_in_totals(self, calculator):
        inv = [
            {
                "provider": "aws",
                "account_id": "x",
                "region": "us-east-1",
                "resource_type": "unknown:thing",
                "count": 99,
            }
        ]
        results = calculator.calculate(inv)
        assert results["summary"]["totals"].get("Unsupported", 0) == 99
        assert results["summary"]["hybrid_units"] == 0

    def test_repeated_calculate_resets_unsupported(self, calculator, sample_inventory):
        inv_unknown = [
            {
                "provider": "aws",
                "account_id": "x",
                "region": "r",
                "resource_type": "phantom:thing",
                "count": 1,
            }
        ]
        calculator.calculate(inv_unknown)
        assert ("aws", "phantom:thing") in calculator.get_unsupported_types()

        calculator.calculate(sample_inventory)
        assert ("aws", "phantom:thing") not in calculator.get_unsupported_types()


# --- calculate_from_file ---

class TestCalculateFromFile:
    def test_valid_file(self, calculator, sample_inventory):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(sample_inventory, f)
            f.flush()
            path = f.name

        try:
            results = calculator.calculate_from_file(path)
            assert results["summary"]["totals"]["IaaS"] == 13
        finally:
            os.unlink(path)

    def test_invalid_json_type(self, calculator):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"not": "a list"}, f)
            f.flush()
            path = f.name

        try:
            with pytest.raises(ValueError, match="JSON array"):
                calculator.calculate_from_file(path)
        finally:
            os.unlink(path)

    def test_file_not_found(self, calculator):
        with pytest.raises(FileNotFoundError):
            calculator.calculate_from_file("/nonexistent/path.json")
