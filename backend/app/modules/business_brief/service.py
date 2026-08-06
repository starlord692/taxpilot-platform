"""Application service for assembling the read-only Business Brief boundary."""

from app.modules.business_brief.exceptions import (
    BusinessBriefAccessDeniedError,
    BusinessBriefSourceMismatchError,
)
from app.modules.business_brief.models import (
    BriefNarrative,
    BusinessBrief,
    BusinessBriefRequest,
    CanonicalSignal,
    SignalKind,
)
from app.modules.business_brief.ports import (
    BusinessBriefAuditRepository,
    BusinessBriefAuthorization,
    BusinessBriefContextProvider,
    BusinessBriefMaterialReader,
    BusinessConfidenceReader,
    BusinessHealthReader,
    BusinessMomentumReader,
)


class LegacyBusinessBriefService:
    """Assemble a traceable Business Brief from authoritative read-only sources.

    This service does not calculate canonical signals, invoke AI, execute actions,
    write business data, or define persistence behavior.
    """

    def __init__(
        self,
        *,
        authorization: BusinessBriefAuthorization,
        context_provider: BusinessBriefContextProvider,
        health_reader: BusinessHealthReader,
        momentum_reader: BusinessMomentumReader,
        confidence_reader: BusinessConfidenceReader,
        material_reader: BusinessBriefMaterialReader,
        audit_repository: BusinessBriefAuditRepository | None = None,
    ) -> None:
        """Initialize the boundary with contracts owned by canonical services."""
        self._authorization = authorization
        self._context_provider = context_provider
        self._health_reader = health_reader
        self._momentum_reader = momentum_reader
        self._confidence_reader = confidence_reader
        self._material_reader = material_reader
        self._audit_repository = audit_repository

    async def get_brief(self, request: BusinessBriefRequest) -> BusinessBrief:
        """Return a traceable point-in-time Brief for an authorized business context."""
        allowed = await self._authorization.can_access(
            business_id=request.business_id,
            user_id=request.user_id,
        )
        if not allowed:
            raise BusinessBriefAccessDeniedError("Business Brief access is denied")

        context = await self._context_provider.get_context(
            business_id=request.business_id,
            as_of=request.as_of,
        )
        if context.business_id != request.business_id:
            raise BusinessBriefSourceMismatchError(
                "Business Brief context does not match the requested business"
            )

        health = await self._health_reader.get_health(
            business_id=request.business_id,
            as_of=request.as_of,
        )
        momentum = await self._momentum_reader.get_momentum(
            business_id=request.business_id,
            as_of=request.as_of,
        )
        confidence = await self._confidence_reader.get_confidence(
            business_id=request.business_id,
            as_of=request.as_of,
        )
        self._ensure_signal(health, SignalKind.HEALTH)
        self._ensure_signal(momentum, SignalKind.MOMENTUM)
        self._ensure_signal(confidence, SignalKind.CONFIDENCE)

        material_items = await self._material_reader.list_material_items(
            business_id=request.business_id,
            as_of=request.as_of,
        )
        brief = BusinessBrief(
            business_id=request.business_id,
            requested_by=request.user_id,
            as_of=request.as_of,
            context=context,
            narrative=BriefNarrative(
                current_understanding=context.current_understanding,
                health=health,
                momentum=momentum,
                confidence=confidence,
                material_items=material_items,
            ),
        )
        if self._audit_repository is not None:
            await self._audit_repository.record_retrieval(brief)
        return brief

    @staticmethod
    def _ensure_signal(signal: CanonicalSignal, expected_kind: SignalKind) -> None:
        """Prevent canonical signal roles from being conflated at the boundary."""
        if signal.kind != expected_kind:
            raise BusinessBriefSourceMismatchError(
                f"Expected {expected_kind.value}, received {signal.kind.value}"
            )


class BusinessBriefService:
    """ES-001 production boundary routed through the ES-007 facade.

    This boundary preserves the ES-001 request contract while delegating all
    canonical Brief retrieval and compatibility projection to the temporary,
    one-way ES-007 migration facade. It does not retain legacy assembly logic.
    """

    def __init__(
        self,
        *,
        compatibility_facade: "BusinessBriefCompatibilityFacade",
    ) -> None:
        """Initialize the production experience boundary with the approved facade."""
        self._compatibility_facade = compatibility_facade

    async def get_brief(self, request: BusinessBriefRequest) -> BusinessBrief:
        """Delegate the unchanged ES-001 request to the production facade path."""
        return await self._compatibility_facade.get_brief(request)


from app.modules.business_brief.migration.facade import (  # noqa: E402
    BusinessBriefCompatibilityFacade,
)