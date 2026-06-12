"""Unit tests for the AccessRuleEnforcer service."""

import pytest

from app.services.ingestion.access_rules import AccessResult, AccessRuleEnforcer
from app.utils.department_config import DEPARTMENTS, SENSITIVITY_MATRIX


@pytest.fixture
def enforcer() -> AccessRuleEnforcer:
    return AccessRuleEnforcer()


class TestValidateDepartment:
    """Tests for department existence validation."""

    def test_valid_department(self, enforcer: AccessRuleEnforcer):
        assert enforcer._validate_department("finance") is True
        assert enforcer._validate_department("logistic") is True
        assert enforcer._validate_department("demand_supply") is True
        assert enforcer._validate_department("accounting_tax") is True

    def test_invalid_department(self, enforcer: AccessRuleEnforcer):
        assert enforcer._validate_department("nonexistent") is False
        assert enforcer._validate_department("") is False
        assert enforcer._validate_department("Finance") is False  # case-sensitive


class TestValidateSubfolder:
    """Tests for subfolder validity within a department."""

    def test_valid_subfolder(self, enforcer: AccessRuleEnforcer):
        assert enforcer._validate_subfolder("finance", "cashflow") is True
        assert enforcer._validate_subfolder("finance", "payments") is True
        assert enforcer._validate_subfolder("logistic", "inbound") is True

    def test_none_subfolder_is_valid(self, enforcer: AccessRuleEnforcer):
        assert enforcer._validate_subfolder("finance", None) is True

    def test_invalid_subfolder(self, enforcer: AccessRuleEnforcer):
        assert enforcer._validate_subfolder("finance", "nonexistent") is False
        assert enforcer._validate_subfolder("finance", "inbound") is False  # belongs to logistic

    def test_subfolder_from_wrong_department(self, enforcer: AccessRuleEnforcer):
        # "invoices" belongs to accounting_tax, not finance
        assert enforcer._validate_subfolder("finance", "invoices") is False


class TestCheckConfidentialAccess:
    """Tests for confidential access authorization."""

    def test_authorized_with_token(self, enforcer: AccessRuleEnforcer):
        assert enforcer._check_confidential_access("finance", "payments", "admin-token") is True

    def test_denied_without_auth(self, enforcer: AccessRuleEnforcer):
        assert enforcer._check_confidential_access("finance", "payments", None) is False

    def test_denied_with_empty_auth(self, enforcer: AccessRuleEnforcer):
        assert enforcer._check_confidential_access("finance", "payments", "") is False

    def test_denied_with_whitespace_auth(self, enforcer: AccessRuleEnforcer):
        assert enforcer._check_confidential_access("finance", "payments", "   ") is False


class TestEnforce:
    """Integration tests for the full enforce() method."""

    def test_valid_department_no_subfolder(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("finance", None)
        assert result.is_allowed is True
        assert result.sensitivity_level == "Internal"
        assert result.error_code is None

    def test_valid_department_valid_subfolder_internal(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("accounting_tax", "invoices")
        assert result.is_allowed is True
        assert result.sensitivity_level == "Internal"

    def test_valid_department_valid_subfolder_public_internal(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("logistic", "sops")
        assert result.is_allowed is True
        assert result.sensitivity_level == "Public_Internal"

    def test_confidential_subfolder_with_auth(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("finance", "payments", "valid-auth-token")
        assert result.is_allowed is True
        assert result.sensitivity_level == "Confidential"

    def test_confidential_subfolder_without_auth(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("finance", "payments", None)
        assert result.is_allowed is False
        assert result.error_code == "CONFIDENTIAL_ACCESS_DENIED"
        assert result.sensitivity_level is None

    def test_invalid_department(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("nonexistent", None)
        assert result.is_allowed is False
        assert result.error_code == "INVALID_DEPARTMENT"
        assert "nonexistent" in result.error_message

    def test_invalid_subfolder(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("finance", "nonexistent")
        assert result.is_allowed is False
        assert result.error_code == "INVALID_SUBFOLDER"
        assert "nonexistent" in result.error_message

    def test_invalid_department_takes_priority_over_subfolder(self, enforcer: AccessRuleEnforcer):
        """If department is invalid, we don't even check subfolder."""
        result = enforcer.enforce("bad_dept", "bad_sub")
        assert result.is_allowed is False
        assert result.error_code == "INVALID_DEPARTMENT"

    def test_result_details_on_success(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("demand_supply", "forecasts")
        assert result.is_allowed is True
        assert result.details["department"] == "demand_supply"
        assert result.details["subfolder"] == "forecasts"
        assert result.details["sensitivity_level"] == "Internal"

    def test_result_details_on_invalid_department(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("bad", None)
        assert "valid_departments" in result.details
        assert "finance" in result.details["valid_departments"]

    def test_result_details_on_invalid_subfolder(self, enforcer: AccessRuleEnforcer):
        result = enforcer.enforce("finance", "bad_sub")
        assert "valid_subfolders" in result.details
        assert "cashflow" in result.details["valid_subfolders"]

    def test_all_confidential_subfolders_require_auth(self, enforcer: AccessRuleEnforcer):
        """Every subfolder in the Confidential sensitivity list should require auth."""
        confidential_subs = SENSITIVITY_MATRIX["Confidential"]
        for sub in confidential_subs:
            # Find which department this subfolder belongs to
            for dept, subs in DEPARTMENTS.items():
                if sub in subs:
                    result = enforcer.enforce(dept, sub, None)
                    assert result.is_allowed is False, (
                        f"{dept}/{sub} should require auth"
                    )
                    assert result.error_code == "CONFIDENTIAL_ACCESS_DENIED"
                    break
