"""Access rule enforcement for the ingestion pipeline.

Verifies department existence, subfolder validity, and sensitivity-level
authorization before a file proceeds through the pipeline.

Integrates with app.utils.department_config for department/subfolder lookups
and sensitivity level resolution.
"""

import logging
from dataclasses import dataclass, field

from app.utils.department_config import (
    DEPARTMENTS,
    SENSITIVITY_MATRIX,
    get_subfolder_sensitivity,
)

logger = logging.getLogger(__name__)


@dataclass
class AccessResult:
    """Result of access rule enforcement.

    Attributes:
        is_allowed: Whether the submission passed all access rule checks.
        sensitivity_level: The resolved sensitivity level for the target subfolder
            (set on success).
        error_code: Machine-readable error code if access was denied.
        error_message: Human-readable description of the rule violation.
        details: Additional context about the access decision.
    """

    is_allowed: bool
    sensitivity_level: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    details: dict = field(default_factory=dict)


class AccessRuleEnforcer:
    """Enforces department access rules during ingestion validation.

    Checks that:
    1. The department exists in the configured department list.
    2. The subfolder (if provided) is valid for the specified department.
    3. If the subfolder has "Confidential" sensitivity, the submitting source
       has explicit authorization for confidential ingestion.
    """

    def enforce(
        self,
        department: str,
        subfolder: str | None,
        source_auth: str | None = None,
    ) -> AccessResult:
        """Enforce access rules for a file submission.

        Args:
            department: The target department identifier.
            subfolder: The target subfolder within the department (optional).
            source_auth: Authorization token/identifier for confidential access
                (optional). Must be provided when targeting a confidential subfolder.

        Returns:
            AccessResult indicating success with resolved sensitivity level,
            or failure with the specific rule violation.
        """
        # Step 1: Validate department exists
        if not self._validate_department(department):
            return AccessResult(
                is_allowed=False,
                error_code="INVALID_DEPARTMENT",
                error_message=f"Department '{department}' does not exist in the configured department list.",
                details={"department": department, "valid_departments": list(DEPARTMENTS.keys())},
            )

        # Step 2: Validate subfolder (if provided)
        if subfolder is not None and not self._validate_subfolder(department, subfolder):
            valid_subfolders = DEPARTMENTS.get(department, [])
            return AccessResult(
                is_allowed=False,
                error_code="INVALID_SUBFOLDER",
                error_message=f"Subfolder '{subfolder}' is not valid for department '{department}'.",
                details={
                    "department": department,
                    "subfolder": subfolder,
                    "valid_subfolders": valid_subfolders,
                },
            )

        # Step 3: Resolve sensitivity level and check confidential access
        sensitivity_level = self._resolve_sensitivity(subfolder)

        if sensitivity_level == "Confidential":
            if not self._check_confidential_access(department, subfolder, source_auth):
                return AccessResult(
                    is_allowed=False,
                    error_code="CONFIDENTIAL_ACCESS_DENIED",
                    error_message=(
                        f"Subfolder '{subfolder}' has 'Confidential' sensitivity level. "
                        "Explicit authorization is required for confidential ingestion."
                    ),
                    details={
                        "department": department,
                        "subfolder": subfolder,
                        "sensitivity_level": "Confidential",
                        "authorization_provided": source_auth is not None,
                    },
                )

        # All checks passed
        return AccessResult(
            is_allowed=True,
            sensitivity_level=sensitivity_level,
            details={
                "department": department,
                "subfolder": subfolder,
                "sensitivity_level": sensitivity_level,
            },
        )

    def _validate_department(self, department: str) -> bool:
        """Check if the department exists in the configured department list.

        Args:
            department: The department identifier to validate.

        Returns:
            True if the department exists, False otherwise.
        """
        return department in DEPARTMENTS

    def _validate_subfolder(self, department: str, subfolder: str | None) -> bool:
        """Check if the subfolder is valid for the specified department.

        Args:
            department: The department identifier (assumed already validated).
            subfolder: The subfolder to validate within the department.

        Returns:
            True if the subfolder is valid for the department, False otherwise.
            Returns True if subfolder is None (no subfolder specified).
        """
        if subfolder is None:
            return True

        valid_subfolders = DEPARTMENTS.get(department, [])
        return subfolder in valid_subfolders

    def _check_confidential_access(
        self,
        department: str,
        subfolder: str | None,
        source_auth: str | None,
    ) -> bool:
        """Check if the source has explicit authorization for confidential ingestion.

        A submission targeting a subfolder with "Confidential" sensitivity level
        must provide a non-empty source_auth value to be authorized.

        Args:
            department: The target department identifier.
            subfolder: The target subfolder.
            source_auth: The authorization token/identifier. Must be a non-empty
                string to grant access.

        Returns:
            True if the source is authorized for confidential access, False otherwise.
        """
        # source_auth must be a non-empty string to authorize confidential access
        if source_auth is None or source_auth.strip() == "":
            return False
        return True

    def _resolve_sensitivity(self, subfolder: str | None) -> str:
        """Resolve the sensitivity level for a given subfolder.

        Uses the SENSITIVITY_MATRIX from department_config to determine
        the sensitivity level. Defaults to "Internal" if the subfolder
        is not found in any sensitivity category or if no subfolder is specified.

        Args:
            subfolder: The subfolder to resolve sensitivity for.

        Returns:
            The sensitivity level string ("Confidential", "Internal", or "Public_Internal").
        """
        if subfolder is None:
            return "Internal"
        return get_subfolder_sensitivity(subfolder)
