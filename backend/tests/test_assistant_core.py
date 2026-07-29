"""Tests for AI-001 assistant orchestration foundation."""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Self, cast

import pytest

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.assistant.events import AssistantToolExecutedEvent
from app.modules.assistant.models import (
    ApprovalLevel,
    ApprovalStatus,
    AssistantApproval,
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantEntityReference,
    AssistantExecutionPlan,
    AssistantExecutionStep,
    AssistantMessage,
    AssistantRun,
    AssistantRunStatus,
    AssistantToolCall,
    AssistantWorkflow,
    AssistantWorkflowStatus,
    AssistantWorkflowType,
    ContextSource,
    ContextType,
    ConversationStatus,
    EntityResolutionConfidence,
    ExecutionMode,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
    ExecutionStepStatus,
    MessageRole,
    ToolCallStatus,
    ToolSideEffect,
)
from app.modules.assistant.providers import MockAssistantProvider
from app.modules.assistant.schemas import AssistantMessageRequest
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import (
    AssistantToolExecutor,
    AssistantToolRegistry,
    GetBusinessContextTool,
    ToolContext,
)
from app.modules.business.api.context import BusinessContext
from app.modules.business.models import (
    Business,
    BusinessMembership,
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)
from app.modules.identity.models import IdentityUser


class FakeBusinessRepository:
    """Fake business repository for assistant service tests."""

    def __init__(self, business: Business | None) -> None:
        self._business = business

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return the configured business when the id matches."""
        if self._business is None or self._business.id != business_id:
            return None
        return self._business


class FakeBusinessMembershipRepository:
    """Fake membership repository for assistant service tests."""

    def __init__(self, membership: BusinessMembership | None) -> None:
        self._membership = membership

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return the configured membership when both ids match."""
        if self._membership is None:
            return None
        if (
            self._membership.business_id == business_id
            and self._membership.user_id == user_id
        ):
            return self._membership
        return None


class FakeAssistantConversationRepository:
    """In-memory assistant repository used by service tests."""

    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, AssistantConversation] = {}
        self.messages: list[AssistantMessage] = []
        self.runs: list[AssistantRun] = []
        self.tool_calls: list[AssistantToolCall] = []
        self.context_snapshots: list[AssistantContextSnapshot] = []
        self.execution_plans: list[AssistantExecutionPlan] = []
        self.execution_steps: list[AssistantExecutionStep] = []
        self.approvals: list[AssistantApproval] = []
        self.entity_references: list[AssistantEntityReference] = []
        self.workflows: list[AssistantWorkflow] = []

    async def create_conversation(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
        language: str,
        timezone: str,
    ) -> AssistantConversation:
        """Create an in-memory conversation."""
        conversation = AssistantConversation(
            id=uuid.uuid4(),
            business_id=business_id,
            user_id=user_id,
            title=title,
            language=language,
            timezone=timezone,
            status=ConversationStatus.ACTIVE,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.conversations[conversation.id] = conversation
        return conversation

    async def get_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantConversation | None:
        """Return a matching in-memory conversation."""
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            return None
        if conversation.business_id == business_id and conversation.user_id == user_id:
            return conversation
        return None

    async def add_message(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AssistantMessage:
        """Add an in-memory message."""
        message = AssistantMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata or {},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.messages.append(message)
        return message

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 20,
    ) -> list[AssistantMessage]:
        """Return recent in-memory messages."""
        messages = [
            message
            for message in self.messages
            if message.conversation_id == conversation_id
        ]
        return messages[-limit:]

    async def create_run(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        prompt_version: str,
        provider_name: str,
        model_name: str,
    ) -> AssistantRun:
        """Create an in-memory assistant run."""
        run = AssistantRun(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            status=AssistantRunStatus.RUNNING,
            prompt_version=prompt_version,
            provider_name=provider_name,
            model_name=model_name,
            input_tokens=0,
            output_tokens=0,
            started_at=utc_now(),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.runs.append(run)
        return run

    async def complete_run(
        self,
        run: AssistantRun,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> AssistantRun:
        """Mark an in-memory run completed."""
        run.status = AssistantRunStatus.COMPLETED
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.latency_ms = latency_ms
        run.completed_at = utc_now()
        return run

    async def fail_run(
        self,
        run: AssistantRun,
        *,
        failure_reason: str,
    ) -> AssistantRun:
        """Mark an in-memory run failed."""
        run.status = AssistantRunStatus.FAILED
        run.failure_reason = failure_reason
        run.completed_at = utc_now()
        return run

    async def create_tool_call(
        self,
        *,
        run_id: uuid.UUID,
        tool_name: str,
        input_payload: dict[str, object],
        required_business_context: bool,
        side_effect: ToolSideEffect,
    ) -> AssistantToolCall:
        """Create an in-memory tool-call audit row."""
        tool_call = AssistantToolCall(
            id=uuid.uuid4(),
            run_id=run_id,
            tool_name=tool_name,
            input_payload=input_payload,
            required_business_context=required_business_context,
            side_effect=side_effect,
            status=ToolCallStatus.PENDING,
            started_at=utc_now(),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.tool_calls.append(tool_call)
        return tool_call

    async def complete_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantToolCall:
        """Mark an in-memory tool call completed."""
        tool_call.status = ToolCallStatus.COMPLETED
        tool_call.output_payload = output_payload
        tool_call.latency_ms = latency_ms
        tool_call.completed_at = utc_now()
        return tool_call

    async def fail_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        error_code: str,
        latency_ms: int,
    ) -> AssistantToolCall:
        """Mark an in-memory tool call failed."""
        tool_call.status = ToolCallStatus.FAILED
        tool_call.error_code = error_code
        tool_call.latency_ms = latency_ms
        tool_call.completed_at = utc_now()
        return tool_call

    async def update_summary(
        self,
        conversation: AssistantConversation,
        *,
        summary: str,
    ) -> AssistantConversation:
        """Update an in-memory conversation summary."""
        conversation.summary = summary
        return conversation

    async def list_recent_tool_calls(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 5,
    ) -> list[AssistantToolCall]:
        """Return recent completed in-memory tool calls."""
        _ = conversation_id
        return [
            tool_call
            for tool_call in self.tool_calls
            if tool_call.status == ToolCallStatus.COMPLETED
        ][-limit:]

    async def create_context_snapshot(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        context_version: str,
        context_type: ContextType,
        payload: dict[str, object],
        provenance: dict[str, object],
        expires_at: datetime,
    ) -> AssistantContextSnapshot:
        """Create an in-memory context snapshot."""
        snapshot = AssistantContextSnapshot(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            context_version=context_version,
            context_type=context_type,
            payload=payload,
            provenance=provenance,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.context_snapshots.append(snapshot)
        return snapshot

    async def create_entity_reference(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID | None,
        entity_label: str,
        source: ContextSource,
        confidence: EntityResolutionConfidence,
        confidence_score: float,
        provenance: dict[str, object],
        expires_at: datetime,
    ) -> AssistantEntityReference:
        """Create an in-memory entity reference."""
        reference = AssistantEntityReference(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            source=source,
            confidence=confidence,
            confidence_score=confidence_score,
            provenance=provenance,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.entity_references.append(reference)
        return reference

    async def list_active_entity_references(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[AssistantEntityReference]:
        """Return active in-memory entity references."""
        references = [
            reference
            for reference in self.entity_references
            if reference.conversation_id == conversation_id
            and reference.business_id == business_id
            and reference.user_id == user_id
            and reference.expires_at > now
            and (entity_type is None or reference.entity_type == entity_type)
        ]
        return references[-limit:]

    async def get_active_workflow(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
    ) -> AssistantWorkflow | None:
        """Return the latest active in-memory workflow."""
        active_statuses = {
            AssistantWorkflowStatus.ACTIVE,
            AssistantWorkflowStatus.WAITING_FOR_USER,
            AssistantWorkflowStatus.EXECUTING_TOOLS,
            AssistantWorkflowStatus.READY_FOR_ACTION,
        }
        for workflow in reversed(self.workflows):
            if (
                workflow.conversation_id == conversation_id
                and workflow.business_id == business_id
                and workflow.user_id == user_id
                and workflow.status in active_statuses
                and workflow.expires_at > now
            ):
                return workflow
        return None

    async def create_workflow(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        workflow_type: AssistantWorkflowType,
        status: AssistantWorkflowStatus,
        current_step: str,
        active_entity_refs: list[dict[str, object]],
        pending_decisions: list[dict[str, object]],
        provenance: dict[str, object],
        expires_at: datetime,
    ) -> AssistantWorkflow:
        """Create an in-memory workflow."""
        workflow = AssistantWorkflow(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            workflow_type=workflow_type,
            status=status,
            current_step=current_step,
            active_entity_refs=active_entity_refs,
            pending_decisions=pending_decisions,
            provenance=provenance,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.workflows.append(workflow)
        return workflow

    async def transition_workflow(
        self,
        workflow: AssistantWorkflow,
        *,
        status: AssistantWorkflowStatus,
        current_step: str,
        active_entity_refs: list[dict[str, object]],
        pending_decisions: list[dict[str, object]],
        provenance: dict[str, object],
        expires_at: datetime,
    ) -> AssistantWorkflow:
        """Transition an in-memory workflow."""
        workflow.status = status
        workflow.current_step = current_step
        workflow.active_entity_refs = active_entity_refs
        workflow.pending_decisions = pending_decisions
        workflow.provenance = provenance
        workflow.expires_at = expires_at
        return workflow

    async def get_completed_execution_plan_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantExecutionPlan | None:
        """Return a completed execution plan for idempotent replay."""
        for plan in self.execution_plans:
            if (
                plan.business_id == business_id
                and plan.idempotency_key == idempotency_key
                and plan.status == ExecutionPlanStatus.COMPLETED
            ):
                plan.steps = [
                    step for step in self.execution_steps if step.plan_id == plan.id
                ]
                return plan
        return None

    async def create_execution_plan(
        self,
        *,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        plan_version: str,
        planner_version: str,
        normalization_version: str,
        prompt_version: str,
        context_version: str,
        status: ExecutionPlanStatus,
        execution_mode: ExecutionMode,
        policy_decision: ExecutionPolicyDecision,
        approval_level: ApprovalLevel,
        approval_status: ApprovalStatus,
        idempotency_key: str,
        normalized_plan: dict[str, object],
        policy_reasons: list[object],
        provenance: dict[str, object],
        correlation_id: str,
    ) -> AssistantExecutionPlan:
        """Create an in-memory execution plan."""
        plan = AssistantExecutionPlan(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            run_id=run_id,
            business_id=business_id,
            user_id=user_id,
            plan_version=plan_version,
            planner_version=planner_version,
            normalization_version=normalization_version,
            prompt_version=prompt_version,
            context_version=context_version,
            status=status,
            execution_mode=execution_mode,
            policy_decision=policy_decision,
            approval_level=approval_level,
            approval_status=approval_status,
            idempotency_key=idempotency_key,
            normalized_plan=normalized_plan,
            policy_reasons=policy_reasons,
            provenance=provenance,
            correlation_id=correlation_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.execution_plans.append(plan)
        return plan

    async def update_execution_plan_status(
        self,
        plan: AssistantExecutionPlan,
        *,
        status: ExecutionPlanStatus,
        failure_reason: str | None = None,
    ) -> AssistantExecutionPlan:
        """Update an in-memory execution plan status."""
        plan.status = status
        plan.failure_reason = failure_reason
        if status in {
            ExecutionPlanStatus.COMPLETED,
            ExecutionPlanStatus.FAILED,
            ExecutionPlanStatus.BLOCKED,
        }:
            plan.completed_at = utc_now()
        return plan

    async def create_execution_step(
        self,
        *,
        plan_id: uuid.UUID,
        step_order: int,
        tool_name: str,
        capability_name: str,
        tool_manifest_version: str,
        input_payload: dict[str, object],
        required_business_context: bool,
        side_effect: ToolSideEffect,
        idempotency_key: str,
        dependencies: list[object],
        provenance: dict[str, object],
    ) -> AssistantExecutionStep:
        """Create an in-memory execution step."""
        step = AssistantExecutionStep(
            id=uuid.uuid4(),
            plan_id=plan_id,
            step_order=step_order,
            tool_name=tool_name,
            capability_name=capability_name,
            tool_manifest_version=tool_manifest_version,
            input_payload=input_payload,
            required_business_context=required_business_context,
            side_effect=side_effect,
            idempotency_key=idempotency_key,
            dependencies=dependencies,
            provenance=provenance,
            status=ExecutionStepStatus.PENDING,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.execution_steps.append(step)
        return step

    async def mark_execution_step_running(
        self,
        step: AssistantExecutionStep,
    ) -> AssistantExecutionStep:
        """Mark an in-memory execution step as running."""
        step.status = ExecutionStepStatus.RUNNING
        step.started_at = utc_now()
        return step

    async def complete_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        tool_call_id: uuid.UUID,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantExecutionStep:
        """Mark an in-memory execution step as completed."""
        step.status = ExecutionStepStatus.COMPLETED
        step.tool_call_id = tool_call_id
        step.output_payload = output_payload
        step.latency_ms = latency_ms
        step.completed_at = utc_now()
        return step

    async def fail_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        error_code: str,
        failure_reason: str,
        latency_ms: int | None = None,
    ) -> AssistantExecutionStep:
        """Mark an in-memory execution step as failed."""
        step.status = ExecutionStepStatus.FAILED
        step.error_code = error_code
        step.failure_reason = failure_reason
        step.latency_ms = latency_ms
        step.completed_at = utc_now()
        return step

    async def create_approval_checkpoint(
        self,
        *,
        plan_id: uuid.UUID,
        business_id: uuid.UUID,
        requested_by: uuid.UUID,
        approval_level: ApprovalLevel,
        status: ApprovalStatus,
        reason: str,
        plan_hash: str,
        provenance: dict[str, object],
        expires_at: datetime,
    ) -> AssistantApproval:
        """Create an in-memory approval checkpoint."""
        approval = AssistantApproval(
            id=uuid.uuid4(),
            plan_id=plan_id,
            business_id=business_id,
            requested_by=requested_by,
            approval_level=approval_level,
            status=status,
            reason=reason,
            plan_hash=plan_hash,
            provenance=provenance,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.approvals.append(approval)
        return approval

class FakeAssistantUnitOfWork:
    """Fake UOW that satisfies assistant and business-context protocols."""

    def __init__(
        self,
        *,
        business: Business,
        membership: BusinessMembership,
        assistant_conversations: FakeAssistantConversationRepository,
    ) -> None:
        self.businesses = FakeBusinessRepository(business)
        self.business_memberships = FakeBusinessMembershipRepository(membership)
        self.assistant_conversations = assistant_conversations
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self) -> Self:
        """Enter the fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the fake transaction scope."""
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        """Record a fake commit."""
        self.commit_count += 1

    async def rollback(self) -> None:
        """Record a fake rollback."""
        self.rollback_count += 1


def build_identity_user(user_id: uuid.UUID) -> IdentityUser:
    """Build an identity user for assistant tests."""
    return IdentityUser(
        id=user_id,
        email="owner@example.com",
        first_name="Tax",
        last_name="Pilot",
        display_name="Tax Pilot",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def build_business(business_id: uuid.UUID) -> Business:
    """Build an active business for assistant tests."""
    return Business(
        id=business_id,
        business_code="BUS-001",
        legal_name="Pilot Books Private Limited",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        status=BusinessStatus.ACTIVE,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def build_membership(
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> BusinessMembership:
    """Build a business membership for assistant tests."""
    return BusinessMembership(
        id=uuid.uuid4(),
        business_id=business_id,
        user_id=user_id,
        role="OWNER",
        created_at=utc_now(),
        updated_at=utc_now(),
    )


@pytest.mark.asyncio
async def test_business_context_tool_returns_authoritative_context() -> None:
    """Business tool output comes from the validated business context only."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    context = BusinessContext(business=business, membership=membership, user=user)

    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    executor = AssistantToolExecutor(registry)

    result = await executor.execute(
        tool_name="business.get_context",
        arguments={},
        context=ToolContext(current_user=user, business_context=context),
    )

    assert result.tool_name == "business.get_context"
    assert result.result["business_id"] == str(business_id)
    assert result.result["legal_name"] == "Pilot Books Private Limited"
    assert result.result["membership_role"] == "OWNER"


@pytest.mark.asyncio
async def test_assistant_service_orchestrates_grounded_business_response() -> None:
    """Assistant service validates context, executes a tool, and audits the run."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    repository = FakeAssistantConversationRepository()
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    dispatcher = EventDispatcher()
    tool_events: list[AssistantToolExecutedEvent] = []
    dispatcher.register(AssistantToolExecutedEvent, tool_events.append)
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    service = AssistantService(
        # The fake UOW is intentionally structural; this cast keeps the test double
        # decoupled from SQLAlchemy while preserving the production protocol.
        unit_of_work_factory=cast(Callable[[], AssistantUnitOfWork], lambda: uow),
        event_dispatcher=dispatcher,
        provider=MockAssistantProvider(),
        tool_registry=registry,
        prompt_builder=PromptBuilder(),
    )

    response = await service.send_message(
        request=AssistantMessageRequest(
            business_id=business_id,
            message="What business context am I using?",
        ),
        current_user=user,
    )

    assert response.conversation_id in repository.conversations
    assert response.run.status == AssistantRunStatus.COMPLETED
    assert response.run.prompt_version == "assistant-context-v1"
    assert response.message.role == MessageRole.ASSISTANT
    assert "Pilot Books Private Limited" in response.message.content
    assert response.tool_calls[0].tool_name == "business.get_context"
    assert response.tool_calls[0].side_effect == ToolSideEffect.READ
    assert uow.commit_count == 1
    assert len(tool_events) == 1


def test_assistant_openapi_routes_are_registered() -> None:
    """Assistant endpoints are exposed through the application OpenAPI schema."""
    app = create_app(initialize_resources=False)
    openapi = app.openapi()

    assert "/api/v1/assistant/messages" in openapi["paths"]
    assert "/api/v1/assistant/conversations/{conversation_id}" in openapi["paths"]







