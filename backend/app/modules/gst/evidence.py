"""GSTIN verification evidence lifecycle and freshness policy under TAX-01.

Enforces strict separation between:
- FORMAT_VALIDATED_UNVERIFIED: deterministic regex/checksum pass; unverified.
- REGISTRATION_VERIFIED: confirmed by an approved, independent verification source.
- INVALIDATED: explicitly revoked or invalidated by legal status/identity change.

Enforces default freshness policy lock:
Without an approved tenant freshness policy, verification evidence cannot
authorize invoice issuance, failing closed with
`sales.invoice_freshness_policy_undefined`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.common.exceptions import ValidationException
from app.core.config import get_settings


class BuyerRegistrationUnverifiedException(ValidationException):
    """Raised when buyer GSTIN is not confirmed as REGISTRATION_VERIFIED."""

    status_code = 422
    error_code = "sales.invoice_buyer_registration_unconfirmed"


BuyerRegistrationUnconfirmedException = BuyerRegistrationUnverifiedException


class FreshnessPolicyUndefinedException(ValidationException):
    """Raised when tenant has no approved freshness policy configured."""

    status_code = 422
    error_code = "sales.invoice_freshness_policy_undefined"


class BuyerRegistrationStaleException(ValidationException):
    """Raised when verification evidence exceeds the approved maximum age."""

    status_code = 422
    error_code = "sales.invoice_buyer_registration_stale"


class BuyerRegistrationInvalidatedException(ValidationException):
    """Raised when registration evidence has been invalidated or cancelled."""

    status_code = 422
    error_code = "sales.invoice_buyer_registration_invalidated"


class GSTINEvidenceStatus(StrEnum):
    """Epistemic evidence lifecycle status for GSTIN registrations."""

    FORMAT_VALIDATED_UNVERIFIED = "FORMAT_VALIDATED_UNVERIFIED"
    REGISTRATION_VERIFIED = "REGISTRATION_VERIFIED"
    INVALIDATED = "INVALIDATED"


class FreshnessPolicy(BaseModel):
    """Tenant-configured freshness policy governing registration evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_approved: bool = Field(
        default=False,
        description="Whether policy has received formal tenant governance approval.",
    )
    max_age_days: int | None = Field(
        default=None,
        description="Maximum permissible evidence age in calendar days.",
        ge=1,
    )


# Ratified live production verification providers for Milestone 1.
# Under FD-TAX-01-05-A / Milestone 1 governance, NO live production GSP or NIC
# provider is authorized or ratified. This set is deliberately empty (fail-closed).
AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES: frozenset[str] = frozenset()

# Approved sandbox / testbed verification providers permitted in non-production
# environments (testing, development).
APPROVED_TESTBED_VERIFICATION_SOURCES: frozenset[str] = frozenset(
    {"SANDBOX_GST_VERIFIER"}
)


def is_authorized_verification_source(
    evidence_source: str | None,
    *,
    environment: str | None = None,
) -> bool:
    """Check if source is authorized to produce REGISTRATION_VERIFIED evidence.

    In Milestone 1:
    - In production, staging, live, or any non-testbed environment, NO live
      provider is ratified. Any source returns False.
    - In explicit testing and development environments, only approved testbed sources
      (e.g., 'SANDBOX_GST_VERIFIER') are authorized.
    - Arbitrary, caller-controlled, mock, manual-extract, or unratified sources
      never qualify.
    """
    if not evidence_source or not isinstance(evidence_source, str):
        return False

    clean_source = evidence_source.strip().upper()

    env = environment
    if env is None:
        try:
            env = get_settings().environment
        except Exception:
            env = "production"

    clean_env = str(env).strip().lower()

    # Explicit permitted non-production test contexts only:
    if clean_env in ("testing", "development", "test", "dev"):
        return clean_source in APPROVED_TESTBED_VERIFICATION_SOURCES

    # In production, staging, live, prod, or any other/unknown environment,
    # strictly evaluate against AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES
    # (empty in Milestone 1 -> fail closed).
    return clean_source in AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES


class GSTINVerificationEvidence(BaseModel):
    """Auditable evidence record for GSTIN registration verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gstin: str = Field(description="15-character GSTIN.")
    status: GSTINEvidenceStatus = Field(
        default=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        description="Current evidence lifecycle status.",
    )
    evidence_source: str | None = Field(
        default=None,
        description=(
            "Independent external verification source "
            "(e.g. sandbox verifier, portal extract)."
        ),
    )
    verified_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when independent verification was obtained.",
    )
    internal_reviewer_identity: str | None = Field(
        default=None,
        description=(
            "Internal reviewer identity (for audit logging only; "
            "does NOT replace external source)."
        ),
    )
    evidence_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured verification payload metadata.",
    )

    def is_verified(self, *, environment: str | None = None) -> bool:
        """Return True only if confirmed REGISTRATION_VERIFIED with an approved source.

        In Milestone 1, no production live provider is authorized.
        Only explicit approved testbed/sandbox providers (e.g. SANDBOX_GST_VERIFIER
        in non-production environments) can certify REGISTRATION_VERIFIED.
        Arbitrary, caller-controlled, mock, manual-extract, or unratified sources
        are strictly prohibited.
        """
        if not is_authorized_verification_source(
            self.evidence_source, environment=environment
        ):
            return False
        return (
            self.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED
            and self.verified_at is not None
        )


def evaluate_buyer_registration_evidence(
    *,
    evidence: GSTINVerificationEvidence | None,
    freshness_policy: FreshnessPolicy | None,
    as_of: datetime | None = None,
    environment: str | None = None,
) -> None:
    """Evaluate buyer registration evidence against freshness and status invariants.

    Raises:
        BuyerRegistrationUnverifiedException: If unverified or unapproved.
        BuyerRegistrationInvalidatedException: If evidence status is INVALIDATED.
        FreshnessPolicyUndefinedException: If freshness policy unapproved/undefined.
        BuyerRegistrationStaleException: If verified evidence exceeds max_age_days.
    """
    if evidence is None:
        raise BuyerRegistrationUnverifiedException(
            "Buyer GSTIN registration evidence is missing or unverified",
            details={"reason": "NO_EVIDENCE_SUPPLIED"},
        )

    if evidence.status == GSTINEvidenceStatus.INVALIDATED:
        raise BuyerRegistrationInvalidatedException(
            "Buyer GSTIN registration has been invalidated or cancelled",
            details={"gstin": evidence.gstin},
        )

    if evidence.status != GSTINEvidenceStatus.REGISTRATION_VERIFIED:
        raise BuyerRegistrationUnverifiedException(
            f"Buyer GSTIN status is {evidence.status.value}, which does not establish "
            "verified registration",
            details={
                "gstin": evidence.gstin,
                "status": evidence.status.value,
            },
        )

    if not evidence.evidence_source or evidence.verified_at is None:
        raise BuyerRegistrationUnverifiedException(
            "Buyer GSTIN lacks independent verification source or timestamp",
            details={"gstin": evidence.gstin},
        )

    # Invariant: Authoritative evidence trust boundary check (allowlist, not denylist).
    # Rejects arbitrary, mock, manual-extract, or unratified sources.
    if not is_authorized_verification_source(
        evidence.evidence_source, environment=environment
    ):
        raise BuyerRegistrationUnverifiedException(
            f"Evidence source '{evidence.evidence_source}' is not an authorized "
            "statutory verification source",
            details={
                "gstin": evidence.gstin,
                "evidence_source": evidence.evidence_source,
                "environment": environment or "default",
            },
        )

    # Invariant: Tenant reviewer approval alone does not constitute verification
    if (
        not freshness_policy
        or not freshness_policy.is_approved
        or freshness_policy.max_age_days is None
    ):
        raise FreshnessPolicyUndefinedException(
            "Tenant freshness policy is unapproved or undefined; "
            "verified registration cannot authorize issuance",
            details={
                "gstin": evidence.gstin,
                "policy_approved": getattr(freshness_policy, "is_approved", False),
            },
        )

    current_time = as_of or datetime.now(UTC)
    if evidence.verified_at.tzinfo is None:
        verified_at = evidence.verified_at.replace(tzinfo=UTC)
    else:
        verified_at = evidence.verified_at

    age = current_time - verified_at
    if age > timedelta(days=freshness_policy.max_age_days):
        raise BuyerRegistrationStaleException(
            f"Buyer registration evidence is {age.days} days old, "
            f"exceeding policy limit of {freshness_policy.max_age_days} days",
            details={
                "gstin": evidence.gstin,
                "age_days": age.days,
                "max_age_days": freshness_policy.max_age_days,
                "verified_at": verified_at.isoformat(),
            },
        )
