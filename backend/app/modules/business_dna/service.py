"""Deterministic assembly service for authoritative Business DNA context.

The service validates and assembles declared or explicitly approved context. It
does not infer missing information, calculate a profile, evaluate the business,
retrieve data, persist results, call AI, or expose an API.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.business_dna.models import (
    BusinessDNAContext,
    BusinessIdentityProfile,
    ComplianceProfile,
    FinancialProfile,
    OperationalProfile,
    StrategicProfile,
)


@dataclass(frozen=True, slots=True)
class BusinessDNAContextInput:
    """Authoritative descriptive input used to assemble Business DNA context."""

    business_id: uuid.UUID
    revision: int
    recorded_at: datetime
    identity: BusinessIdentityProfile
    operational: OperationalProfile
    financial: FinancialProfile
    compliance: ComplianceProfile
    strategic: StrategicProfile


class BusinessDNAService:
    """Assemble validated Business DNA from authoritative descriptive inputs only."""

    def assemble(self, context_input: BusinessDNAContextInput) -> BusinessDNAContext:
        """Return immutable context without deriving any business characteristic."""
        self._validate_source_timing(context_input)
        return BusinessDNAContext(
            business_id=context_input.business_id,
            revision=context_input.revision,
            recorded_at=context_input.recorded_at,
            identity=context_input.identity,
            operational=context_input.operational,
            financial=context_input.financial,
            compliance=context_input.compliance,
            strategic=context_input.strategic,
        )

    @staticmethod
    def _validate_source_timing(context_input: BusinessDNAContextInput) -> None:
        """Ensure each declared source predates or matches the recorded context."""
        provenances = (
            context_input.identity.provenance,
            context_input.operational.provenance,
            context_input.financial.provenance,
            context_input.compliance.provenance,
            context_input.strategic.provenance,
        )
        if any(
            provenance.effective_at > context_input.recorded_at
            for provenance in provenances
        ):
            raise ValueError(
                "Business DNA provenance cannot be effective after recorded context"
            )
