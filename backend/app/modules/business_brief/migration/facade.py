"""Temporary one-way ES-007 compatibility facade for Business Brief.

The facade authorizes an ES-001 request, obtains an ES-006 canonical Brief,
validates the migration-owned descriptor, and returns a legacy-compatible
response with the exact canonical Brief and explanation embedded. It contains
no policy, selection, ranking, generation, AI, repository, persistence, API,
or source-capability behavior.
"""

from uuid import UUID

from app.modules.business_brief.es006.explanation import (
    BusinessBriefExplanation as CanonicalBusinessBriefExplanation,
)
from app.modules.business_brief.es006.explanation import (
    BusinessBriefExplanationEngine,
)
from app.modules.business_brief.es006.models import (
    BusinessBrief as CanonicalBusinessBrief,
)
from app.modules.business_brief.es006.models import (
    BusinessBriefNarrativeItem,
    BusinessBriefSourceKind,
    BusinessBriefSourceReference,
)
from app.modules.business_brief.es006.ports import BusinessBriefInputProvider
from app.modules.business_brief.es006.service import (
    BusinessBriefInput,
    BusinessBriefService,
)
from app.modules.business_brief.exceptions import (
    BusinessBriefAccessDeniedError,
    BusinessBriefSourceMismatchError,
)
from app.modules.business_brief.migration.projection import (
    BusinessBriefCompatibilityContextAlias,
    BusinessBriefCompatibilityProjectionDescriptor,
    BusinessBriefCompatibilityProjectionProvider,
    BusinessBriefCompatibilitySignalAlias,
)
from app.modules.business_brief.models import (
    BriefNarrative,
    BusinessBrief,
    BusinessBriefContext,
    BusinessBriefRequest,
    CanonicalSignal,
    EvidenceReference,
    NarrativeStatement,
    SignalKind,
)
from app.modules.business_brief.ports import (
    BusinessBriefAuditRepository,
    BusinessBriefAuthorization,
)


class BusinessBriefCompatibilityFacade:
    """Expose ES-006 output through the temporary ES-001 experience boundary."""

    def __init__(
        self,
        *,
        authorization: BusinessBriefAuthorization,
        canonical_input_provider: BusinessBriefInputProvider,
        projection_provider: BusinessBriefCompatibilityProjectionProvider,
        canonical_service: BusinessBriefService | None = None,
        explanation_engine: BusinessBriefExplanationEngine | None = None,
        audit_repository: BusinessBriefAuditRepository | None = None,
    ) -> None:
        """Initialize the one-way compatibility boundary with published contracts."""
        self._authorization = authorization
        self._canonical_input_provider = canonical_input_provider
        self._projection_provider = projection_provider
        self._canonical_service = canonical_service or BusinessBriefService()
        self._explanation_engine = (
            explanation_engine or BusinessBriefExplanationEngine()
        )
        self._audit_repository = audit_repository

    async def get_brief(self, request: BusinessBriefRequest) -> BusinessBrief:
        """Return an ES-001-compatible response backed by ES-006 output only."""
        allowed = await self._authorization.can_access(
            business_id=request.business_id,
            user_id=request.user_id,
        )
        if not allowed:
            raise BusinessBriefAccessDeniedError("Business Brief access is denied")

        canonical_input = await self._canonical_input_provider.provide_input(
            business_id=request.business_id,
            brief_at=request.as_of,
        )
        self._validate_input(request=request, canonical_input=canonical_input)
        canonical_brief = self._canonical_service.assemble(canonical_input)
        canonical_explanation = self._explanation_engine.explain(brief=canonical_brief)
        descriptor = await self._projection_provider.provide_descriptor(
            business_id=request.business_id,
            brief_at=request.as_of,
            canonical_brief=canonical_brief,
        )
        self._validate_descriptor_identity(
            request=request,
            canonical_brief=canonical_brief,
            descriptor=descriptor,
        )
        try:
            self._validate_descriptor(
                request=request,
                canonical_brief=canonical_brief,
                descriptor=descriptor,
            )
        except BusinessBriefSourceMismatchError as error:
            result = self._unavailable_response(
                request=request,
                canonical_brief=canonical_brief,
                canonical_explanation=canonical_explanation,
                limitation=str(error),
            )
        else:
            result = self._available_response(
                request=request,
                canonical_brief=canonical_brief,
                canonical_explanation=canonical_explanation,
                descriptor=descriptor,
            )
        if self._audit_repository is not None:
            await self._audit_repository.record_retrieval(result)
        return result

    @staticmethod
    def _available_response(
        *,
        request: BusinessBriefRequest,
        canonical_brief: CanonicalBusinessBrief,
        canonical_explanation: CanonicalBusinessBriefExplanation,
        descriptor: BusinessBriefCompatibilityProjectionDescriptor,
    ) -> BusinessBrief:
        """Build validated aliases while preserving the canonical payload exactly."""
        return BusinessBrief(
            business_id=request.business_id,
            requested_by=request.user_id,
            as_of=request.as_of,
            context=BusinessBriefCompatibilityFacade._context_alias(
                business_id=request.business_id,
                alias=descriptor.context,
            ),
            narrative=BriefNarrative(
                current_understanding=BusinessBriefCompatibilityFacade._statement(
                    descriptor.context.current_understanding
                ),
                health=BusinessBriefCompatibilityFacade._signal_alias(
                    alias=descriptor.health,
                    expected_kind=BusinessBriefSourceKind.BUSINESS_HEALTH,
                    legacy_kind=SignalKind.HEALTH,
                ),
                momentum=BusinessBriefCompatibilityFacade._signal_alias(
                    alias=descriptor.momentum,
                    expected_kind=BusinessBriefSourceKind.BUSINESS_MOMENTUM,
                    legacy_kind=SignalKind.MOMENTUM,
                ),
                confidence=BusinessBriefCompatibilityFacade._signal_alias(
                    alias=descriptor.confidence,
                    expected_kind=BusinessBriefSourceKind.BUSINESS_CONFIDENCE,
                    legacy_kind=SignalKind.CONFIDENCE,
                ),
                material_items=(),
            ),
            canonical_brief=canonical_brief,
            canonical_explanation=canonical_explanation,
            projection_status="available",
            projection_limitations=canonical_brief.limitations,
        )

    @staticmethod
    def _unavailable_response(
        *,
        request: BusinessBriefRequest,
        canonical_brief: CanonicalBusinessBrief,
        canonical_explanation: CanonicalBusinessBriefExplanation,
        limitation: str,
    ) -> BusinessBrief:
        """Return canonical output without inventing an unavailable legacy alias."""
        return BusinessBrief(
            business_id=request.business_id,
            requested_by=request.user_id,
            as_of=request.as_of,
            context=None,
            narrative=None,
            canonical_brief=canonical_brief,
            canonical_explanation=canonical_explanation,
            projection_status="unavailable",
            projection_limitations=canonical_brief.limitations
            + (f"Compatibility projection unavailable: {limitation}",),
        )

    @staticmethod
    def _validate_input(
        *, request: BusinessBriefRequest, canonical_input: BusinessBriefInput
    ) -> None:
        """Ensure canonical assembly input is scoped to the authorized request."""
        if canonical_input.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief input does not match the requested business"
            )
        if canonical_input.brief_at != request.as_of:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief input does not match the requested point in time"
            )

    @staticmethod
    def _validate_descriptor_identity(
        *,
        request: BusinessBriefRequest,
        canonical_brief: CanonicalBusinessBrief,
        descriptor: BusinessBriefCompatibilityProjectionDescriptor,
    ) -> None:
        """Reject cross-business or cross-time data before alias handling."""
        if descriptor.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Compatibility projection does not match the requested business"
            )
        if descriptor.brief_at != request.as_of:
            raise BusinessBriefSourceMismatchError(
                "Compatibility projection does not match the requested point in time"
            )
        if canonical_brief.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief does not match the requested business"
            )
        if canonical_brief.brief_at != request.as_of:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief does not match the requested point in time"
            )

    @staticmethod
    def _validate_descriptor(
        *,
        request: BusinessBriefRequest,
        canonical_brief: CanonicalBusinessBrief,
        descriptor: BusinessBriefCompatibilityProjectionDescriptor,
    ) -> None:
        """Validate direct descriptor membership without selecting alternatives."""
        if descriptor.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Compatibility projection does not match the requested business"
            )
        if descriptor.brief_at != request.as_of:
            raise BusinessBriefSourceMismatchError(
                "Compatibility projection does not match the requested point in time"
            )
        if canonical_brief.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief does not match the requested business"
            )
        if canonical_brief.brief_at != request.as_of:
            raise BusinessBriefSourceMismatchError(
                "Canonical Brief does not match the requested point in time"
            )

        narrative_items = canonical_brief.narrative_items
        all_references = tuple(
            reference
            for item in narrative_items
            for reference in item.source_references
        )
        BusinessBriefCompatibilityFacade._validate_context_alias(
            alias=descriptor.context,
            narrative_items=narrative_items,
            all_references=all_references,
        )
        BusinessBriefCompatibilityFacade._validate_signal_alias(
            alias=descriptor.health,
            expected_kind=BusinessBriefSourceKind.BUSINESS_HEALTH,
            narrative_items=narrative_items,
        )
        BusinessBriefCompatibilityFacade._validate_signal_alias(
            alias=descriptor.momentum,
            expected_kind=BusinessBriefSourceKind.BUSINESS_MOMENTUM,
            narrative_items=narrative_items,
        )
        BusinessBriefCompatibilityFacade._validate_signal_alias(
            alias=descriptor.confidence,
            expected_kind=BusinessBriefSourceKind.BUSINESS_CONFIDENCE,
            narrative_items=narrative_items,
        )

    @staticmethod
    def _validate_context_alias(
        *,
        alias: BusinessBriefCompatibilityContextAlias,
        narrative_items: tuple[BusinessBriefNarrativeItem, ...],
        all_references: tuple[BusinessBriefSourceReference, ...],
    ) -> None:
        """Require all context alias structures to already exist canonically."""
        if alias.current_understanding not in narrative_items:
            raise BusinessBriefSourceMismatchError(
                "Compatibility context item is not present in the canonical Brief"
            )
        context_references = (
            alias.business_dna + alias.business_season + alias.business_goals
        )
        if any(reference not in all_references for reference in context_references):
            raise BusinessBriefSourceMismatchError(
                "Compatibility context reference is not present in the canonical Brief"
            )

    @staticmethod
    def _validate_signal_alias(
        *,
        alias: BusinessBriefCompatibilitySignalAlias,
        expected_kind: BusinessBriefSourceKind,
        narrative_items: tuple[BusinessBriefNarrativeItem, ...],
    ) -> None:
        """Require an explicit, matching source reference for each legacy signal."""
        if alias.narrative_item not in narrative_items:
            raise BusinessBriefSourceMismatchError(
                "Compatibility signal item is not present in the canonical Brief"
            )
        if alias.source_reference not in alias.narrative_item.source_references:
            raise BusinessBriefSourceMismatchError(
                "Compatibility signal reference is not present in its canonical item"
            )
        if alias.source_reference.kind is not expected_kind:
            raise BusinessBriefSourceMismatchError(
                "Compatibility signal reference does not match its legacy signal kind"
            )

    @staticmethod
    def _context_alias(
        *,
        business_id: UUID,
        alias: BusinessBriefCompatibilityContextAlias,
    ) -> BusinessBriefContext:
        """Build legacy context wrappers from explicitly referenced structures only."""
        return BusinessBriefContext(
            business_id=business_id,
            current_understanding=BusinessBriefCompatibilityFacade._statement(
                alias.current_understanding
            ),
            business_dna=tuple(
                BusinessBriefCompatibilityFacade._reference(reference)
                for reference in alias.business_dna
            ),
            business_season=tuple(
                BusinessBriefCompatibilityFacade._reference(reference)
                for reference in alias.business_season
            ),
            business_goals=tuple(
                BusinessBriefCompatibilityFacade._reference(reference)
                for reference in alias.business_goals
            ),
        )

    @staticmethod
    def _signal_alias(
        *,
        alias: BusinessBriefCompatibilitySignalAlias,
        expected_kind: BusinessBriefSourceKind,
        legacy_kind: SignalKind,
    ) -> CanonicalSignal:
        """Build a legacy signal wrapper without recalculating canonical meaning."""
        if alias.source_reference.kind is not expected_kind:
            raise BusinessBriefSourceMismatchError(
                "Compatibility signal reference does not match its legacy signal kind"
            )
        return CanonicalSignal(
            kind=legacy_kind,
            statement=BusinessBriefCompatibilityFacade._statement(alias.narrative_item),
            assessed_at=alias.source_reference.effective_at,
        )

    @staticmethod
    def _statement(item: BusinessBriefNarrativeItem) -> NarrativeStatement:
        """Preserve a canonical statement and its explicit limitations unchanged."""
        return NarrativeStatement(
            text=item.statement,
            evidence=tuple(
                BusinessBriefCompatibilityFacade._reference(reference)
                for reference in item.source_references
            ),
            limitations=item.limitations,
        )

    @staticmethod
    def _reference(reference: BusinessBriefSourceReference) -> EvidenceReference:
        """Expose a non-authoritative legacy traceability alias for one source."""
        return EvidenceReference(
            source=reference.source_owner,
            reference=reference.reference,
            description=reference.description,
        )
