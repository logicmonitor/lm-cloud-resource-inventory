"""Tests for base collector utilities."""
# pylint: disable=protected-access,broad-exception-raised

import json
import os
import tempfile

import pytest

from src.collectors.base import (
    require_import,
    retry_api_call,
    _is_transient,
    BaseCollector,
)


# --- require_import ---

class TestRequireImport:
    def test_imports_existing_module(self):
        mod = require_import("json", "json", "test")
        assert hasattr(mod, "dumps")

    def test_imports_submodule(self):
        mod = require_import("os.path", "os", "test")
        assert hasattr(mod, "join")

    def test_raises_helpful_error_for_missing(self):
        with pytest.raises(ImportError, match=r'-m pip install "lm-cloud-inventory'):
            require_import("nonexistent_pkg_xyz", "nonexistent-pkg", "aws")

    def test_error_includes_provider(self):
        with pytest.raises(ImportError, match=r"\[azure\]"):
            require_import("nonexistent_pkg_xyz", "nonexistent-pkg", "azure")


# --- _is_transient ---

class TestIsTransient:
    def test_throttle_keyword(self):
        assert _is_transient(Exception("Request was throttled"))

    def test_429_keyword(self):
        assert _is_transient(Exception("429 Too Many Requests"))

    def test_503_keyword(self):
        assert _is_transient(Exception("503 Service Unavailable"))

    def test_timeout_keyword(self):
        assert _is_transient(Exception("Connection timed out"))
        assert _is_transient(TimeoutError("timeout"))

    def test_auth_error_not_transient(self):
        assert not _is_transient(Exception("Access Denied"))

    def test_permission_error_not_transient(self):
        assert not _is_transient(PermissionError("Forbidden"))


# --- retry_api_call ---

class TestRetryApiCall:
    def test_succeeds_first_try(self):
        result = retry_api_call(lambda: 42)
        assert result == 42

    def test_retries_on_transient_then_succeeds(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 Too Many Requests")
            return "ok"

        result = retry_api_call(flaky, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 3

    def test_raises_immediately_for_non_transient(self):
        def bad():
            raise PermissionError("Access Denied")

        with pytest.raises(PermissionError):
            retry_api_call(bad, max_retries=3, base_delay=0.01)

    def test_exhausts_retries(self):
        def always_fail():
            raise Exception("503 Service Unavailable")

        with pytest.raises(Exception, match="503"):
            retry_api_call(always_fail, max_retries=2, base_delay=0.01)

    def test_passes_args_and_kwargs(self):
        def adder(a, b, extra=0):
            return a + b + extra

        result = retry_api_call(adder, 1, 2, extra=10)
        assert result == 13


# --- BaseCollector ---

class ConcreteCollector(BaseCollector):
    """Minimal concrete implementation for testing abstract base."""

    PROVIDER = "test"

    def collect(self):
        return []

    def validate_permissions(self):
        return True

    def get_account_id(self):
        return "test-account"


class TestBaseCollector:
    def test_create_inventory_record(self):
        c = ConcreteCollector()
        record = c.create_inventory_record(
            account_id="acct-1",
            region="us-east-1",
            resource_type="test:resource",
            count=5,
        )
        assert record["provider"] == "test"
        assert record["account_id"] == "acct-1"
        assert record["region"] == "us-east-1"
        assert record["resource_type"] == "test:resource"
        assert record["count"] == 5
        assert "timestamp" in record

    def test_save_inventory_with_explicit_data(self):
        c = ConcreteCollector()
        data = [{"provider": "test", "count": 1}]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            c.save_inventory(path, data)
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data
        finally:
            os.unlink(path)

    def test_save_inventory_with_empty_list(self):
        c = ConcreteCollector()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            c.save_inventory(path, [])
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == []
        finally:
            os.unlink(path)

    def test_save_inventory_falls_back_to_internal(self):
        c = ConcreteCollector()
        c._inventory = [{"provider": "test", "count": 99}]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            c.save_inventory(path)
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == c._inventory
        finally:
            os.unlink(path)

    def test_print_summary_with_empty_list(self, capsys):
        c = ConcreteCollector()
        c.print_summary([])
        captured = capsys.readouterr()
        assert "Total Resources: 0" in captured.out
