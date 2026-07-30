"""Tests for AI-007 assistant guided action drafting."""

import uuid
from collections.abc import Callable
from typing import Self, cast

import pytest

from app.common.events import EventDispatcher
from app.modules.assistant.actions.adapters import DomainActionResult
from app.modules.assistant.actions.capabilities import ActionCapabilityRegistry
from app.modules.assistant.actions.enums import (
    ActionReadinessStatus,
    AssistantActionStatus,
    AssistantActionType,
)
from app.modules.assistant.actions.events import (
    AssistantActionCompletedEvent,
    AssistantActionDraftCreatedEvent,
)
from app.modules.assistant.actions.exceptions import (
    AssistantActionConflictException,
    AssistantActionValidationException,
)
from app.modules.assistant.actions.manifests import ActionManifestRegistry
from app.modules.assistant.actions.models import (
    AssistantActionDraft,
    AssistantActionResult,
)
from app.modules.assistant.actions.schemas import ActionDraftCreate
from app.modules.assistant.actions.service import (
    AssistantActionService,
    AssistantActionUnitOfWork,
)
from app.modules.assistant.actions.tools import (
    CreateActionDraftTool,
    ExecuteApprovedActionTool,
    GetActionPreviewTool,
)
from app.modules.assistant.api.dependencies import get_tool_registry
from app.modules.assistant.models import ApprovalLevel, ToolSideEffect
from app.modules.business.api.context import BusinessContext
from tests.test_assistant_core import (
    build_business,
    build_identity_user,
    build_membership,
)


class FakeActionRepository:
    """In-memory action draft repository."""

    def __init__(self) -> None:
        self.drafts: list[AssistantActionDraft] = []

    async def create_draft(self, draft: AssistantActionDraft) -> AssistantActionDraft:
        """Persist an action draft in memory."""
        draft.id = uuid.uuid4()
        self.drafts.append(draft)
        return draft

    async def get_by_id(
        self,
        *,
        draft_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> AssistantActionDraft | None:
        """Return a business-scoped draft."""
        for draft in self.drafts:
            if draft.id == draft_id and draft.business_id == business_id:
                return draft
        return None

    async def get_active_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantActionDraft | None:
        """Return a matching active draft."""
        for draft in self.drafts:
            if (
                draft.business_id == business_id
                and draft.idempotency_key == idempotency_key
            ):
                return draft
        return None

    async def update_draft(self, draft: AssistantActionDraft) -> AssistantActionDraft:
        """Return the updated draft."""
        return draft


class FakeActionResultRepository:
    """In-memory action result repository."""

    def __init__(self) -> None:
        self.results: list[AssistantActionResult] = []

    async def create_result(
        self, result: AssistantActionResult
    ) -> AssistantActionResult:
        """Persist an action result in memory."""
        result.id = uuid.uuid4()
        self.results.append(result)
        return result

    async def list_by_draft(self, draft_id: uuid.UUID) -> list[AssistantActionResult]:
        """Return results for one draft."""
        return [result for result in self.results if result.draft_id == draft_id]


class FakeActionUnitOfWork:
    """Fake action Unit of Work."""

    def __init__(
        self,
        *,
        actions: FakeActionRepository,
        results: FakeActionResultRepository,
    ) -> None:
        self.assistant_actions = actions
        self.assistant_action_results = results
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        """Enter the fake transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the fake transaction."""
        _ = exc_type
        _ = exc
        _ = traceback

    async def commit(self) -> None:
        """Record a commit."""
        self.commit_count += 1


class FakeDomainAdapter:
    """Domain adapter proving execution is delegated outside assistant persistence."""

    def __init__(self) -> None:
        self.calls: list[tuple[AssistantActionType, dict[str, object]]] = []

    async def execute(
        self,
        *,
        action_type: AssistantActionType,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        """Return a deterministic fake ERP result."""
        self.calls.append((action_type, payload))
        return DomainActionResult(
            erp_record_type="sales_invoice",
            erp_record_id=uuid.uuid4(),
            domain_service="SalesInvoiceService",
            payload={"business_id": str(business_context.business_id)},
        )


def build_business_context() -> BusinessContext:
    """Build a validated business context for action tests."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    return BusinessContext(business=business, membership=membership, user=user)


def build_service(
    *,
    actions: FakeActionRepository | None = None,
    results: FakeActionResultRepository | None = None,
    adapter: FakeDomainAdapter | None = None,
    dispatcher: EventDispatcher | None = None,
) -> tuple[
    AssistantActionService,
    FakeActionRepository,
    FakeActionResultRepository,
    FakeDomainAdapter,
]:
    """Build the action service with in-memory dependencies."""
    action_repo = actions or FakeActionRepository()
    result_repo = results or FakeActionResultRepository()
    domain_adapter = adapter or FakeDomainAdapter()

    def uow_factory() -> FakeActionUnitOfWork:
        return FakeActionUnitOfWork(actions=action_repo, results=result_repo)

    service = AssistantActionService(
        unit_of_work_factory=cast(
            Callable[[], AssistantActionUnitOfWork],
            uow_factory,
        ),
        domain_adapter=domain_adapter,
        event_dispatcher=dispatcher,
    )
    return service, action_repo, result_repo, domain_adapter


def test_action_manifest_and_capability_registries_are_canonical() -> None:
    """Supported actions are declared in separate manifest and capability registries."""
    manifests = ActionManifestRegistry()
    capabilities = ActionCapabilityRegistry()

    manifest = manifests.get(AssistantActionType.SALES_INVOICE_CREATE_DRAFT)
    capability = capabilities.get(AssistantActionType.SALES_INVOICE_CREATE_DRAFT)

    assert manifest.required_service == "SalesInvoiceService"
    assert manifest.side_effect == ToolSideEffect.WRITE
    assert manifest.approval_level == ApprovalLevel.EXPLICIT_USER_APPROVAL
    assert capability.supports_preview is True
    assert capability.supports_approval_gate is True


@pytest.mark.asyncio
async def test_create_action_draft_generates_readiness_and_preview() -> None:
    """Assistant actions begin as drafts with readiness findings and preview."""
    context = build_business_context()
    service, repository, _, _ = build_service()

    draft = await service.create_draft(
        request=ActionDraftCreate(
            business_id=context.business_id,
            conversation_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            action_type=AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
            draft_payload={"data": {"invoice_number": "INV-1"}},
        ),
        business_context=context,
    )

    assert draft in repository.drafts
    assert draft.status == AssistantActionStatus.READY_FOR_APPROVAL
    assert draft.readiness_status == ActionReadinessStatus.NEEDS_APPROVAL
    assert draft.validated_payload == {"data": {"invoice_number": "INV-1"}}
    assert draft.execution_preview is not None
    assert draft.execution_preview["approval_required"] is True
    assert draft.provenance["authority"] == "assistant_action_service"


@pytest.mark.asyncio
async def test_action_draft_rejects_business_context_mismatch() -> None:
    """Draft creation is scoped to the resolved active business context."""
    context = build_business_context()
    service, repository, _, _ = build_service()

    with pytest.raises(AssistantActionValidationException):
        await service.create_draft(
            request=ActionDraftCreate(
                business_id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                action_type=AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
                draft_payload={"data": {"invoice_number": "INV-TENANT"}},
            ),
            business_context=context,
        )

    assert repository.drafts == []

@pytest.mark.asyncio
async def test_action_draft_idempotency_replays_existing_draft() -> None:
    """Duplicate draft requests return the existing draft instead of creating a copy."""
    context = build_business_context()
    service, repository, _, _ = build_service()
    request = ActionDraftCreate(
        business_id=context.business_id,
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        action_type=AssistantActionType.EXPENSE_CREATE_DRAFT,
        draft_payload={"data": {"total": "100.00"}},
    )

    first = await service.create_draft(request=request, business_context=context)
    second = await service.create_draft(request=request, business_context=context)

    assert first is second
    assert len(repository.drafts) == 1


@pytest.mark.asyncio
async def test_unapproved_action_execution_is_rejected() -> None:
    """ERP execution cannot happen before approval."""
    context = build_business_context()
    service, _, _, adapter = build_service()
    draft = await service.create_draft(
        request=ActionDraftCreate(
            business_id=context.business_id,
            conversation_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            action_type=AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
            draft_payload={"data": {"invoice_number": "INV-2"}},
        ),
        business_context=context,
    )

    with pytest.raises(AssistantActionConflictException):
        await service.execute_approved(draft_id=draft.id, business_context=context)

    assert adapter.calls == []


@pytest.mark.asyncio
async def test_approved_action_execution_delegates_to_domain_adapter() -> None:
    """Approved execution delegates to a deterministic domain adapter."""
    context = build_business_context()
    dispatcher = EventDispatcher()
    completed_events: list[AssistantActionCompletedEvent] = []
    dispatcher.register(AssistantActionCompletedEvent, completed_events.append)
    service, _, result_repo, adapter = build_service(dispatcher=dispatcher)
    draft = await service.create_draft(
        request=ActionDraftCreate(
            business_id=context.business_id,
            conversation_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            action_type=AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
            draft_payload={"data": {"invoice_number": "INV-3"}},
        ),
        business_context=context,
    )
    draft.status = AssistantActionStatus.APPROVED

    result = await service.execute_approved(draft_id=draft.id, business_context=context)

    assert adapter.calls == [
        (
            AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
            {"data": {"invoice_number": "INV-3"}},
        )
    ]
    assert result in result_repo.results
    assert result.domain_service == "SalesInvoiceService"
    assert draft.status == AssistantActionStatus.COMPLETED
    assert len(completed_events) == 1


@pytest.mark.asyncio
async def test_action_draft_created_event_is_published() -> None:
    """Draft creation emits action audit events."""
    context = build_business_context()
    dispatcher = EventDispatcher()
    draft_events: list[AssistantActionDraftCreatedEvent] = []
    dispatcher.register(AssistantActionDraftCreatedEvent, draft_events.append)
    service, _, _, _ = build_service(dispatcher=dispatcher)

    await service.create_draft(
        request=ActionDraftCreate(
            business_id=context.business_id,
            conversation_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            action_type=AssistantActionType.VENDOR_CREATE_DRAFT,
            draft_payload={"data": {"name": "Acme"}},
        ),
        business_context=context,
    )

    assert len(draft_events) == 1
    assert draft_events[0].action_type == "vendor.create_draft"


def test_action_tools_are_registered_with_expected_policy_metadata() -> None:
    """Assistant action tools are registered with controlled side-effect metadata."""
    registry = get_tool_registry()

    create_tool = registry.get("assistant.action.create_draft")
    preview_tool = registry.get("assistant.action.get_preview")
    execute_tool = registry.get("assistant.action.execute_approved")

    assert isinstance(create_tool, CreateActionDraftTool)
    assert isinstance(preview_tool, GetActionPreviewTool)
    assert isinstance(execute_tool, ExecuteApprovedActionTool)
    assert create_tool.approval_level == ApprovalLevel.AUTO_ALLOWED
    assert execute_tool.approval_level == ApprovalLevel.EXPLICIT_USER_APPROVAL
    assert execute_tool.side_effect == ToolSideEffect.WRITE





