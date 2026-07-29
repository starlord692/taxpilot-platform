"""Tests for AI-003 assistant tool orchestration."""

import uuid
from collections.abc import Callable
from typing import cast

import pytest
from pydantic import BaseModel

from app.common.events import EventDispatcher
from app.modules.assistant.approvals import ApprovalCheckpointService
from app.modules.assistant.events import (
    AssistantApprovalCheckpointCreatedEvent,
    AssistantExecutionCompletedEvent,
)
from app.modules.assistant.models import (
    ApprovalLevel,
    AssistantRunStatus,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
    MessageRole,
    ToolRetryPolicy,
    ToolSideEffect,
)
from app.modules.assistant.orchestration import AssistantExecutionEngine
from app.modules.assistant.planning import ExecutionPlanner
from app.modules.assistant.policies import ExecutionPolicyEvaluator
from app.modules.assistant.providers import LLMToolCall, MockAssistantProvider
from app.modules.assistant.schemas import AssistantMessageRequest
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import (
    AssistantToolExecutor,
    AssistantToolRegistry,
    EmptyToolInput,
    GetBusinessContextTool,
    ToolContext,
    ToolDefinition,
    ToolResult,
)
from app.modules.business.api.context import BusinessContext
from tests.test_assistant_core import (
    FakeAssistantConversationRepository,
    FakeAssistantUnitOfWork,
    build_business,
    build_identity_user,
    build_membership,
)


class WriteTool:
    """Write-capable test tool used to verify approval gating."""

    name = "test.write"
    description = "A write-capable test tool."
    input_model: type[BaseModel] = EmptyToolInput
    requires_business_context = True
    side_effect = ToolSideEffect.WRITE
    approval_level = ApprovalLevel.EXPLICIT_USER_APPROVAL
    idempotency_required = True
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def definition(self) -> ToolDefinition:
        """Return a capability manifest for the test tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            idempotency_required=self.idempotency_required,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Return a deterministic write result."""
        _ = payload
        _ = context
        return ToolResult(tool_name=self.name, result={"created": True})


@pytest.mark.asyncio
async def test_execution_planner_versions_and_manifest_metadata() -> None:
    """Planner persists reproducible versions and tool manifest metadata."""
    registry = AssistantToolRegistry()
    registry.register(WriteTool())
    planner = ExecutionPlanner(registry)

    plan = planner.build_plan(
        selected_tools=[LLMToolCall(tool_name="test.write", arguments={})],
        prompt_version="assistant-context-v1",
        context_version="assistant-context-v1",
        business_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
    )

    assert plan.plan_version == "assistant-execution-plan-v1"
    assert plan.planner_version == "assistant-planner-v1"
    assert plan.normalization_version == "assistant-plan-normalizer-v1"
    assert plan.steps[0].manifest.manifest_version == "assistant-tool-manifest-v1"
    assert plan.steps[0].manifest.idempotency_required is True


@pytest.mark.asyncio
async def test_execution_policy_requires_approval_for_write_tools() -> None:
    """Policy requires approval before consequential write tools execute."""
    registry = AssistantToolRegistry()
    registry.register(WriteTool())
    planner = ExecutionPlanner(registry)
    plan = planner.build_plan(
        selected_tools=[LLMToolCall(tool_name="test.write")],
        prompt_version="assistant-context-v1",
        context_version="assistant-context-v1",
        business_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
    )

    result = ExecutionPolicyEvaluator().evaluate(plan)

    assert result.decision == ExecutionPolicyDecision.REQUIRES_APPROVAL
    assert result.approval_level == ApprovalLevel.EXPLICIT_USER_APPROVAL


@pytest.mark.asyncio
async def test_execution_engine_creates_approval_checkpoint_without_executing() -> None:
    """Approval-gated plans persist checkpoints and do not run tools."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    context = BusinessContext(business=business, membership=membership, user=user)
    repository = FakeAssistantConversationRepository()
    registry = AssistantToolRegistry()
    registry.register(WriteTool())
    planner = ExecutionPlanner(registry)
    plan = planner.build_plan(
        selected_tools=[LLMToolCall(tool_name="test.write")],
        prompt_version="assistant-context-v1",
        context_version="assistant-context-v1",
        business_id=str(business_id),
        conversation_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
    )
    approval_events: list[AssistantApprovalCheckpointCreatedEvent] = []
    dispatcher = EventDispatcher()
    dispatcher.register(AssistantApprovalCheckpointCreatedEvent, approval_events.append)
    engine = AssistantExecutionEngine(
        tool_executor=AssistantToolExecutor(registry),
        event_dispatcher=dispatcher,
    )

    result = await engine.execute_plan(
        repository=repository,
        plan=plan,
        tool_context=ToolContext(current_user=user, business_context=context),
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        business_id=business_id,
        user_id=user_id,
    )

    assert result.approval_required is True
    assert repository.execution_plans[0].status == ExecutionPlanStatus.APPROVAL_REQUIRED
    assert len(repository.approvals) == 1
    assert repository.tool_calls == []
    assert len(approval_events) == 1


@pytest.mark.asyncio
async def test_assistant_service_persists_execution_plan_for_existing_flow() -> None:
    """AI-001 context response still works through AI-003 orchestration."""
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
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    completion_events: list[AssistantExecutionCompletedEvent] = []
    dispatcher = EventDispatcher()
    dispatcher.register(AssistantExecutionCompletedEvent, completion_events.append)
    service = AssistantService(
        unit_of_work_factory=cast(Callable[[], AssistantUnitOfWork], lambda: uow),
        event_dispatcher=dispatcher,
        provider=MockAssistantProvider(),
        tool_registry=registry,
        prompt_builder=PromptBuilder(),
    )

    response = await service.send_message(
        request=AssistantMessageRequest(
            business_id=business_id,
            message="What company context is active?",
        ),
        current_user=user,
    )

    assert response.run.status == AssistantRunStatus.COMPLETED
    assert response.message.role == MessageRole.ASSISTANT
    assert "Pilot Books Private Limited" in response.message.content
    assert repository.execution_plans[0].status == ExecutionPlanStatus.COMPLETED
    assert repository.execution_steps[0].output_payload is not None
    assert len(completion_events) == 1


@pytest.mark.asyncio
async def test_approval_checkpoint_contains_replay_protection_metadata() -> None:
    """Approval checkpoints bind approval to a specific plan hash."""
    registry = AssistantToolRegistry()
    registry.register(WriteTool())
    plan = ExecutionPlanner(registry).build_plan(
        selected_tools=[LLMToolCall(tool_name="test.write")],
        prompt_version="assistant-context-v1",
        context_version="assistant-context-v1",
        business_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
    )
    policy = ExecutionPolicyEvaluator().evaluate(plan)

    checkpoint = ApprovalCheckpointService().build_checkpoint(
        plan=plan,
        policy_result=policy,
        business_id=str(uuid.uuid4()),
        requested_by=str(uuid.uuid4()),
    )

    assert checkpoint is not None
    assert checkpoint["plan_hash"]
    assert checkpoint["approval_level"] == ApprovalLevel.EXPLICIT_USER_APPROVAL

