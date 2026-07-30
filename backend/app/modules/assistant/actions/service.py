"""Assistant action drafting and controlled execution service."""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

from app.common.events import Event, EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.actions.adapters import (
    DomainActionAdapter,
    UnsupportedDomainActionAdapter,
)
from app.modules.assistant.actions.capabilities import ActionCapabilityRegistry
from app.modules.assistant.actions.enums import (
    ActionReadinessStatus,
    AssistantActionStatus,
)
from app.modules.assistant.actions.events import (
    AssistantActionCompletedEvent,
    AssistantActionDraftCreatedEvent,
    AssistantActionExecutionStartedEvent,
    AssistantActionFailedEvent,
    AssistantActionReadinessValidatedEvent,
    AssistantActionReplayedEvent,
)
from app.modules.assistant.actions.exceptions import (
    AssistantActionConflictException,
    AssistantActionNotFoundException,
    AssistantActionValidationException,
)
from app.modules.assistant.actions.manifests import ActionManifestRegistry
from app.modules.assistant.actions.models import (
    AssistantActionDraft,
    AssistantActionResult,
)
from app.modules.assistant.actions.preview import ExecutionPreviewBuilder
from app.modules.assistant.actions.provenance import ActionProvenanceBuilder
from app.modules.assistant.actions.readiness import ExecutionReadinessValidator
from app.modules.assistant.actions.repository import (
    AssistantActionRepository,
    AssistantActionResultRepository,
)
from app.modules.assistant.actions.schemas import ActionDraftCreate, ExecutionPreview
from app.modules.business.api.context import BusinessContext

ACTION_DRAFT_TTL_HOURS = 24


class AssistantActionUnitOfWork(Protocol):
    """Unit of Work contract for assistant action records."""

    assistant_actions: AssistantActionRepository
    assistant_action_results: AssistantActionResultRepository

    async def __aenter__(self) -> "AssistantActionUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...


AssistantActionUnitOfWorkFactory = Callable[[], AssistantActionUnitOfWork]


class AssistantActionService:
    """Manage draft-first assistant actions and controlled ERP execution."""

    def __init__(
        self,
        *,
        unit_of_work_factory: AssistantActionUnitOfWorkFactory,
        manifests: ActionManifestRegistry | None = None,
        capabilities: ActionCapabilityRegistry | None = None,
        readiness_validator: ExecutionReadinessValidator | None = None,
        preview_builder: ExecutionPreviewBuilder | None = None,
        provenance_builder: ActionProvenanceBuilder | None = None,
        domain_adapter: DomainActionAdapter | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        """Initialize action service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._manifests = manifests or ActionManifestRegistry()
        self._capabilities = capabilities or ActionCapabilityRegistry()
        self._readiness = readiness_validator or ExecutionReadinessValidator(
            manifests=self._manifests,
            capabilities=self._capabilities,
        )
        self._preview = preview_builder or ExecutionPreviewBuilder()
        self._provenance = provenance_builder or ActionProvenanceBuilder()
        self._domain_adapter = domain_adapter or UnsupportedDomainActionAdapter()
        self._event_dispatcher = event_dispatcher

    async def create_draft(
        self,
        *,
        request: ActionDraftCreate,
        business_context: BusinessContext,
    ) -> AssistantActionDraft:
        """Create or replay a draft-first assistant action."""
        if request.business_id != business_context.business_id:
            raise AssistantActionValidationException(
                "Assistant action business does not match the active business context"
            )
        manifest = self._manifests.get(request.action_type)
        capability = self._capabilities.get(request.action_type)
        idempotency_key = self._idempotency_key(
            business_id=business_context.business_id,
            action_type=request.action_type.value,
            payload=request.draft_payload,
            conversation_id=request.conversation_id,
            manifest_version=manifest.manifest_version,
        )
        async with self._unit_of_work_factory() as uow:
            existing = await uow.assistant_actions.get_active_by_idempotency(
                business_id=business_context.business_id,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return existing
            readiness_status, findings, validated_payload = self._readiness.validate(
                action_type=request.action_type,
                draft_payload=request.draft_payload,
                business_context=business_context,
            )
            preview = self._preview.build(
                manifest=manifest,
                readiness_status=readiness_status,
                readiness_findings=findings,
                idempotency_key=idempotency_key,
            )
            draft = AssistantActionDraft(
                business_id=business_context.business_id,
                conversation_id=request.conversation_id,
                run_id=request.run_id,
                created_by_user_id=business_context.user_id,
                action_type=request.action_type,
                manifest_version=manifest.manifest_version,
                capability_version=capability.capability_version,
                status=self._draft_status(readiness_status),
                draft_payload=request.draft_payload,
                validated_payload=validated_payload,
                readiness_status=readiness_status,
                readiness_findings=[
                    finding.model_dump(mode="json") for finding in findings
                ],
                execution_preview=preview.model_dump(mode="json"),
                approval_required=manifest.approval_level.value != "none",
                approval_level=manifest.approval_level,
                idempotency_key=idempotency_key,
                provenance=self._provenance.for_draft(
                    business_context=business_context,
                    conversation_id=request.conversation_id,
                    run_id=request.run_id,
                    action_type=request.action_type.value,
                    source=request.source,
                    manifest_version=manifest.manifest_version,
                    capability_version=capability.capability_version,
                ),
                expires_at=utc_now() + timedelta(hours=ACTION_DRAFT_TTL_HOURS),
            )
            draft = await uow.assistant_actions.create_draft(draft)
            await uow.commit()
            await self._dispatch(
                AssistantActionDraftCreatedEvent(
                    draft_id=draft.id,
                    business_id=draft.business_id,
                    action_type=draft.action_type.value,
                )
            )
            await self._dispatch(
                AssistantActionReadinessValidatedEvent(
                    draft_id=draft.id,
                    business_id=draft.business_id,
                    readiness_status=draft.readiness_status.value,
                )
            )
            return draft

    async def get_draft(
        self,
        *,
        draft_id: uuid.UUID,
        business_context: BusinessContext,
    ) -> AssistantActionDraft:
        """Return one business-scoped assistant action draft."""
        async with self._unit_of_work_factory() as uow:
            draft = await uow.assistant_actions.get_by_id(
                draft_id=draft_id,
                business_id=business_context.business_id,
            )
            if draft is None:
                raise AssistantActionNotFoundException(
                    "Assistant action draft not found"
                )
            return draft

    async def execution_preview(
        self,
        *,
        draft_id: uuid.UUID,
        business_context: BusinessContext,
    ) -> ExecutionPreview:
        """Return the stored execution preview for one action draft."""
        draft = await self.get_draft(
            draft_id=draft_id, business_context=business_context
        )
        if draft.execution_preview is None:
            raise AssistantActionValidationException("Execution preview is unavailable")
        return ExecutionPreview.model_validate(draft.execution_preview)

    async def execute_approved(
        self,
        *,
        draft_id: uuid.UUID,
        business_context: BusinessContext,
    ) -> AssistantActionResult:
        """Execute an approved action through the registered domain service adapter."""
        async with self._unit_of_work_factory() as uow:
            draft = await uow.assistant_actions.get_by_id(
                draft_id=draft_id,
                business_id=business_context.business_id,
            )
            if draft is None:
                raise AssistantActionNotFoundException(
                    "Assistant action draft not found"
                )
            if draft.status == AssistantActionStatus.COMPLETED:
                await self._dispatch(
                    AssistantActionReplayedEvent(
                        draft_id=draft.id,
                        business_id=draft.business_id,
                        idempotency_key=draft.idempotency_key,
                    )
                )
                results = await uow.assistant_action_results.list_by_draft(draft.id)
                if results:
                    return results[-1]
            if draft.status != AssistantActionStatus.APPROVED:
                raise AssistantActionConflictException(
                    "Assistant action must be approved before execution",
                    details={"status": draft.status.value},
                )
            if draft.validated_payload is None:
                raise AssistantActionValidationException(
                    "Assistant action lacks a validated payload"
                )
            draft.status = AssistantActionStatus.EXECUTING
            await uow.assistant_actions.update_draft(draft)
            await self._dispatch(
                AssistantActionExecutionStartedEvent(
                    draft_id=draft.id,
                    business_id=draft.business_id,
                    action_type=draft.action_type.value,
                )
            )
            try:
                domain_result = await self._domain_adapter.execute(
                    action_type=draft.action_type,
                    payload=draft.validated_payload,
                    business_context=business_context,
                )
            except Exception as exc:
                draft.status = AssistantActionStatus.FAILED
                await uow.assistant_actions.update_draft(draft)
                await uow.commit()
                await self._dispatch(
                    AssistantActionFailedEvent(
                        draft_id=draft.id,
                        business_id=draft.business_id,
                        error_code=type(exc).__name__,
                    )
                )
                raise
            draft.status = AssistantActionStatus.COMPLETED
            await uow.assistant_actions.update_draft(draft)
            result = AssistantActionResult.completed(
                draft_id=draft.id,
                business_id=draft.business_id,
                domain_service=domain_result.domain_service,
                result_payload=domain_result.payload,
                erp_record_type=domain_result.erp_record_type,
                erp_record_id=domain_result.erp_record_id,
            )
            result = await uow.assistant_action_results.create_result(result)
            await uow.commit()
            await self._dispatch(
                AssistantActionCompletedEvent(
                    draft_id=draft.id,
                    business_id=draft.business_id,
                    erp_record_type=domain_result.erp_record_type,
                    erp_record_id=domain_result.erp_record_id,
                )
            )
            return result

    def _idempotency_key(
        self,
        *,
        business_id: uuid.UUID,
        action_type: str,
        payload: dict[str, object],
        conversation_id: uuid.UUID,
        manifest_version: str,
    ) -> str:
        """Create a deterministic idempotency key for action drafts."""
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(
            f"{business_id}:{action_type}:{conversation_id}:{manifest_version}:{normalized}".encode()
        ).hexdigest()
        return digest[:128]

    def _draft_status(
        self, readiness_status: ActionReadinessStatus
    ) -> AssistantActionStatus:
        """Map readiness status to draft lifecycle status."""
        if readiness_status == ActionReadinessStatus.BLOCKED:
            return AssistantActionStatus.VALIDATION_FAILED
        if readiness_status == ActionReadinessStatus.NEEDS_APPROVAL:
            return AssistantActionStatus.READY_FOR_APPROVAL
        return AssistantActionStatus.DRAFT

    async def _dispatch(self, event: Event) -> None:
        """Dispatch an event when an event dispatcher is configured."""
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch(event)

