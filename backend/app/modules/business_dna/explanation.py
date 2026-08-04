"""Deterministic structured explanations for authoritative Business DNA context.

This engine preserves profile coverage, provenance, revisions, and limitations.
It does not infer, calculate, evaluate, generate narrative, produce
recommendations, call AI, access repositories, or depend on infrastructure.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.modules.business_dna.models import (
    BusinessDNAContext,
    BusinessDNAProfileProvenance,
)


class BusinessDNAProfileName(StrEnum):
    """The five canonical Business DNA profiles defined by KP-001."""

    IDENTITY = "business_identity"
    OPERATIONAL = "operational_profile"
    FINANCIAL = "financial_profile"
    COMPLIANCE = "compliance_profile"
    STRATEGIC = "strategic_profile"


@dataclass(frozen=True, slots=True)
class BusinessDNAProfileCoverage:
    """Structured provenance and explicit limitations for one canonical profile."""

    profile: BusinessDNAProfileName
    provenance: BusinessDNAProfileProvenance
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BusinessDNAExplanation:
    """Structured, traceable explanation of authoritative Business DNA context."""

    context: BusinessDNAContext
    revision_history: tuple[BusinessDNAContext, ...]
    profile_coverage: tuple[BusinessDNAProfileCoverage, ...]
    limitations: tuple[str, ...]


class BusinessDNAExplanationEngine:
    """Compose a deterministic explanation from authoritative context only."""

    def explain(
        self,
        *,
        context: BusinessDNAContext,
        revision_history: tuple[BusinessDNAContext, ...] = (),
    ) -> BusinessDNAExplanation:
        """Return structured context explanation without adding business meaning."""
        self._validate_revision_history(
            context=context,
            revision_history=revision_history,
        )
        profile_coverage = self._profile_coverage(context)
        return BusinessDNAExplanation(
            context=context,
            revision_history=revision_history,
            profile_coverage=profile_coverage,
            limitations=self._collect_limitations(profile_coverage),
        )

    @staticmethod
    def _validate_revision_history(
        *,
        context: BusinessDNAContext,
        revision_history: tuple[BusinessDNAContext, ...],
    ) -> None:
        """Ensure supplied revision context is complete, consistent, and traceable."""
        if not revision_history:
            return
        if any(item.business_id != context.business_id for item in revision_history):
            raise ValueError("revision history must belong to the explained business")
        revisions = tuple(item.revision for item in revision_history)
        if len(set(revisions)) != len(revisions):
            raise ValueError("revision history must not contain duplicate revisions")
        if context.revision not in revisions:
            raise ValueError("revision history must include the explained context")

    @staticmethod
    def _profile_coverage(
        context: BusinessDNAContext,
    ) -> tuple[BusinessDNAProfileCoverage, ...]:
        """Preserve the five canonical profiles in their approved stable order."""
        profiles = (
            (BusinessDNAProfileName.IDENTITY, context.identity.provenance),
            (BusinessDNAProfileName.OPERATIONAL, context.operational.provenance),
            (BusinessDNAProfileName.FINANCIAL, context.financial.provenance),
            (BusinessDNAProfileName.COMPLIANCE, context.compliance.provenance),
            (BusinessDNAProfileName.STRATEGIC, context.strategic.provenance),
        )
        return tuple(
            BusinessDNAProfileCoverage(
                profile=profile,
                provenance=provenance,
                limitations=provenance.limitations,
            )
            for profile, provenance in profiles
        )

    @staticmethod
    def _collect_limitations(
        coverage: tuple[BusinessDNAProfileCoverage, ...],
    ) -> tuple[str, ...]:
        """Preserve explicit profile limitations in stable, non-repeating order."""
        limitations: list[str] = []
        for profile in coverage:
            limitations.extend(profile.limitations)
        return tuple(dict.fromkeys(limitations))
