"""Transport representations that preserve Business Opportunity authority."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.business_opportunity.models import BusinessOpportunity


class AuthoritativeInputResponse(BaseModel):
    """An unchanged authoritative input reference supplied by the owner."""

    model_config = ConfigDict(extra="forbid")

    source: str
    capability: str
    reference_id: str
    field: str
    value_type: str
    value: Any


class UnavailableOpportunityInformationResponse(BaseModel):
    """Unavailable authoritative information without inferred replacement."""

    model_config = ConfigDict(extra="forbid")

    source: str
    capability: str
    reference_id: str | None
    field: str
    reason: str


class BusinessOpportunityResponse(BaseModel):
    """Read-only presentation of a canonical Business Opportunity."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: UUID
    business_id: UUID
    status: str
    assessment_time: datetime
    opportunity_type: str
    canonical_subject: str
    policy_id: str
    policy_version: str
    eligibility_result: str
    source_references: tuple[AuthoritativeInputResponse, ...]
    evidence: tuple[AuthoritativeInputResponse, ...]
    limitations: tuple[str, ...]
    input_traceability: tuple[AuthoritativeInputResponse, ...]
    provenance: str
    temporal_context: datetime
    unavailable_information: tuple[UnavailableOpportunityInformationResponse, ...]

    @classmethod
    def from_opportunity(
        cls, opportunity: BusinessOpportunity
    ) -> "BusinessOpportunityResponse":
        """Map without selecting, changing, or deriving authoritative content."""
        return cls(
            opportunity_id=opportunity.opportunity_id,
            business_id=opportunity.business_id,
            status=opportunity.status.value,
            assessment_time=opportunity.assessment_time,
            opportunity_type=opportunity.opportunity_type,
            canonical_subject=opportunity.canonical_subject,
            policy_id=opportunity.policy_id,
            policy_version=opportunity.policy_version,
            eligibility_result=opportunity.eligibility_result.value,
            source_references=tuple(
                _authoritative_input(item) for item in opportunity.source_references
            ),
            evidence=tuple(_authoritative_input(item) for item in opportunity.evidence),
            limitations=opportunity.limitations,
            input_traceability=tuple(
                _authoritative_input(item) for item in opportunity.input_traceability
            ),
            provenance=opportunity.provenance,
            temporal_context=opportunity.temporal_context,
            unavailable_information=tuple(
                UnavailableOpportunityInformationResponse(
                    source=item.source,
                    capability=item.capability,
                    reference_id=item.reference_id,
                    field=item.field,
                    reason=item.reason,
                )
                for item in opportunity.unavailable_information
            ),
        )


def _authoritative_input(item: Any) -> AuthoritativeInputResponse:
    """Preserve one owner-published authoritative input without conversion."""
    return AuthoritativeInputResponse(
        source=item.source,
        capability=item.capability,
        reference_id=item.reference_id,
        field=item.field,
        value_type=item.value_type,
        value=item.value,
    )
