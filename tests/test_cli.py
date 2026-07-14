"""Tests for CLI helper functions."""

from src.cli import (
    _warn_irrelevant_options,
    _derive_path,
    _get_all_install_hint,
    _get_install_hint,
    _validate_ids,
    _UUID_RE,
    _GCP_PROJECT_RE,
    _OCID_PREFIX,
)


class TestInstallHints:
    def test_provider_hint_targets_current_interpreter(self):
        assert _get_install_hint("azure").endswith(
            ' -m pip install "lm-cloud-inventory[azure]"'
        )

    def test_all_provider_hint_targets_current_interpreter(self):
        assert _get_all_install_hint().endswith(
            ' -m pip install "lm-cloud-inventory[all]"'
        )


# --- _warn_irrelevant_options ---

class TestWarnIrrelevantOptions:
    def test_no_warning_for_relevant_aws_option(self, capsys):
        _warn_irrelevant_options("aws", profile="prod")
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_warns_for_irrelevant_option(self, capsys):
        _warn_irrelevant_options("aws", compartment="some-ocid")
        captured = capsys.readouterr()
        assert "compartment" in captured.out

    def test_no_warning_for_none_value(self, capsys):
        _warn_irrelevant_options("aws", compartment=None)
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_no_warning_for_empty_tuple(self, capsys):
        _warn_irrelevant_options("azure", subscription=())
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_warns_subscription_for_aws(self, capsys):
        _warn_irrelevant_options("aws", subscription=("sub-1",))
        captured = capsys.readouterr()
        assert "subscription" in captured.out


# --- _derive_path ---

class TestDerivePath:
    def test_add_suffix(self):
        assert _derive_path("out.csv", "_detailed") == "out_detailed.csv"

    def test_change_extension(self):
        assert _derive_path("out.csv", "_inventory", ".json") == "out_inventory.json"

    def test_no_extension(self):
        result = _derive_path("output", "_detailed")
        assert result == "output_detailed"


# --- ID format regexes ---

class TestUUIDRegex:
    def test_valid_uuid(self):
        assert _UUID_RE.match("12345678-1234-1234-1234-123456789abc")

    def test_uppercase_uuid(self):
        assert _UUID_RE.match("12345678-1234-1234-1234-123456789ABC")

    def test_invalid_uuid(self):
        assert not _UUID_RE.match("not-a-uuid")
        assert not _UUID_RE.match("12345678123412341234123456789abc")


class TestGCPProjectRegex:
    def test_valid_project(self):
        assert _GCP_PROJECT_RE.match("my-project-123")

    def test_too_short(self):
        assert not _GCP_PROJECT_RE.match("ab")

    def test_starts_with_number(self):
        assert not _GCP_PROJECT_RE.match("1project")

    def test_uppercase_rejected(self):
        assert not _GCP_PROJECT_RE.match("MyProject")


class TestOCIDPrefix:
    def test_valid_prefix(self):
        ocid = "ocid1.compartment.oc1..aaaaabbbb"
        assert ocid.startswith(_OCID_PREFIX)

    def test_invalid_prefix(self):
        assert not "some-random-id".startswith(_OCID_PREFIX)


# --- _validate_ids ---

class TestValidateIds:
    def test_azure_valid_sub_no_warning(self, capsys):
        _validate_ids("azure", subscription=("12345678-1234-1234-1234-123456789abc",))
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_azure_invalid_sub_warns(self, capsys):
        _validate_ids("azure", subscription=("not-a-guid",))
        captured = capsys.readouterr()
        assert "not-a-guid" in captured.out

    def test_gcp_valid_project_no_warning(self, capsys):
        _validate_ids("gcp", project="my-project-123")
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_gcp_invalid_project_warns(self, capsys):
        _validate_ids("gcp", project="BAD PROJECT")
        captured = capsys.readouterr()
        assert "BAD PROJECT" in captured.out

    def test_oci_valid_ocid_no_warning(self, capsys):
        _validate_ids("oci", compartment="ocid1.compartment.oc1..aaa")
        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_oci_invalid_ocid_warns(self, capsys):
        _validate_ids("oci", compartment="bad-id")
        captured = capsys.readouterr()
        assert "bad-id" in captured.out

    def test_aws_no_validation_needed(self, capsys):
        _validate_ids("aws", profile="anything")
        captured = capsys.readouterr()
        assert "Warning" not in captured.out
