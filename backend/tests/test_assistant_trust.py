"""Tests for AI-005 assistant trust and explainability."""

import uuid
from collections.abc import Callable
from typing import cast

import pytest

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.assistant.events import (
    AssistantGroundingVerifiedEvent,
    AssistantTrustReportGeneratedEvent,
)
from app.modules.assistant.models import (
    ApprovalLevel,
    ApprovalStatus,
    AssistantContextSnapshot,
    AssistantExecutionPlan,
    AssistantExecutionStep,
    AssistantRun,
    AssistantToolCall,
    ContextType,
    ExecutionMode,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
    ExecutionStepStatus,
    MessageRole,
    ToolSideEffect,
)
from app.modules.assistant.tools import ToolContext
from app.modules.assistant.trust import (
    AssistantTrustService,
    ExplainAssistantRunTool,
    GetAssistantConversationAuditTool,
)
from app.modules.assistant.trust.schemas import (
    TRUST_GROUNDING_VERSION,
    TRUST_POLICY_REGISTRY_VERSION,
    TRUST_REPORT_VERSION,
    TRUST_SCORING_VERSION,
    GroundingStatus,
)
from app.modules.assistant.trust.service import AssistantTrustUnitOfWork
from app.modules.business.api.context import BusinessContext
from app.modules.business.exceptions import BusinessNotMemberException
from tests.test_assistant_core import (
    FakeAssistantConversationRepository,
    FakeAssistantUnitOfWork,
    build_business,
    build_identity_user,
    build_membership,
)

HIGH_TRUST_EXPECTATION = 0.9


class FakeTrustRepository(FakeAssistantConversationRepository):
    """Fake assistant repository with AI-005 read methods."""

    async def get_run(
        self,
        *,
        run_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> AssistantRun | None:
        """Return a matching run."""
        for run in self.runs:
            if run.id == run_id and run.conversation_id == conversation_id:
                return run
        return None

    async def list_runs(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantRun]:
        """Return runs for a conversation."""
        return [
            run for run in self.runs if run.conversation_id == conversation_id
        ][:limit]

    async def list_tool_calls_by_run(
        self,
        *,
        run_id: uuid.UUID,
    ) -> list[AssistantToolCall]:
        """Return tool calls for one run."""
        return [
            tool_call for tool_call in self.tool_calls if tool_call.run_id == run_id
        ]

    async def get_execution_plan_by_run(
        self,
        *,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> AssistantExecutionPlan | None:
        """Return the plan for one run."""
        for plan in self.execution_plans:
            if plan.run_id == run_id and plan.business_id == business_id:
                plan.steps = [
                    step for step in self.execution_steps if step.plan_id == plan.id
                ]
                plan.approvals = [
                    approval
                    for approval in self.approvals
                    if approval.plan_id == plan.id
                ]
                return plan
        return None

    async def list_execution_plans_by_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantExecutionPlan]:
        """Return plans for one conversation."""
        plans = [
            plan
            for plan in self.execution_plans
            if (
                plan.conversation_id == conversation_id
                and plan.business_id == business_id
            )
        ][:limit]
        for plan in plans:
            plan.steps = [
                step for step in self.execution_steps if step.plan_id == plan.id
            ]
            plan.approvals = [
                approval for approval in self.approvals if approval.plan_id == plan.id
            ]
        return plans

    async def list_context_snapshots(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantContextSnapshot]:
        """Return scoped context snapshots."""
        return [
            snapshot
            for snapshot in self.context_snapshots
            if snapshot.conversation_id == conversation_id
            and snapshot.business_id == business_id
            and snapshot.user_id == user_id
        ][:limit]


async def _seed_grounded_run(repository: FakeTrustRepository) -> tuple[
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
]:
    """Create a grounded assistant run in the fake repository."""
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conversation = await repository.create_conversation(
        business_id=business_id,
        user_id=user_id,
        title="Trust test",
        language="en",
        timezone="Asia/Calcutta",
    )
    user_message = await repository.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Show business insights",
    )
    run = await repository.create_run(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        prompt_version="assistant-context-v1",
        provider_name="mock",
        model_name="mock-assistant",
    )
    tool_call = await repository.create_tool_call(
        run_id=run.id,
        tool_name="business.generate_insights",
        input_payload={"api_key": "secret-value"},
        required_business_context=True,
        side_effect=ToolSideEffect.READ,
    )
    await repository.complete_tool_call(
        tool_call,
        output_payload={
            "tool_name": "business.generate_insights",
            "result": {
                "confidence": 0.91,
                "evidence": [
                    {
                        "source_type": "financial_statement",
                        "source_service": "FinancialStatementService",
                        "source_id": str(uuid.uuid4()),
                        "source_label": "Profit and Loss",
                        "metric": "net_profit",
                        "value": "1250.00",
                        "generated_at": utc_now().isoformat(),
                    }
                ],
            },
        },
        latency_ms=12,
    )
    await repository.complete_run(
        run,
        input_tokens=20,
        output_tokens=30,
        latency_ms=50,
    )
    plan = AssistantExecutionPlan(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        run_id=run.id,
        business_id=business_id,
        user_id=user_id,
        plan_version="assistant-execution-plan-v1",
        planner_version="assistant-planner-v1",
        normalization_version="assistant-plan-normalizer-v1",
        prompt_version="assistant-context-v1",
        context_version="assistant-context-v1",
        status=ExecutionPlanStatus.COMPLETED,
        execution_mode=ExecutionMode.SINGLE,
        policy_decision=ExecutionPolicyDecision.ALLOWED,
        approval_level=ApprovalLevel.NONE,
        approval_status=ApprovalStatus.NOT_REQUIRED,
        idempotency_key="trust-test",
        normalized_plan={},
        policy_reasons=[],
        provenance={"source": "test"},
        correlation_id="correlation-test",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    repository.execution_plans.append(plan)
    repository.execution_steps.append(
        AssistantExecutionStep(
            id=uuid.uuid4(),
            plan_id=plan.id,
            tool_call_id=tool_call.id,
            step_order=1,
            tool_name="business.generate_insights",
            capability_name="business_insights",
            tool_manifest_version="assistant-tool-manifest-v1",
            input_payload={},
            output_payload=tool_call.output_payload,
            status=ExecutionStepStatus.COMPLETED,
            required_business_context=True,
            side_effect=ToolSideEffect.READ,
            idempotency_key="trust-step",
            dependencies=[],
            provenance={"source": "test"},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    await repository.create_context_snapshot(
        conversation_id=conversation.id,
        business_id=business_id,
        user_id=user_id,
        context_version="assistant-context-v1",
        context_type=ContextType.RUN,
        payload={},
        provenance={"source": "test"},
        expires_at=utc_now(),
    )
    return business_id, user_id, conversation.id, run.id


@pytest.mark.asyncio
async def test_trust_service_explains_grounded_run_with_version_metadata() -> None:
    """Run explanations include versions, evidence, grounding, and redaction."""
    repository = FakeTrustRepository()
    business_id, user_id, conversation_id, run_id = await _seed_grounded_run(repository)
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    dispatcher = EventDispatcher()
    trust_events: list[AssistantTrustReportGeneratedEvent] = []
    grounding_events: list[AssistantGroundingVerifiedEvent] = []
    dispatcher.register(AssistantTrustReportGeneratedEvent, trust_events.append)
    dispatcher.register(AssistantGroundingVerifiedEvent, grounding_events.append)
    service = AssistantTrustService(
        unit_of_work_factory=cast(
            Callable[[], AssistantTrustUnitOfWork],
            lambda: uow,
        ),
        event_dispatcher=dispatcher,
    )

    report = await service.explain_run(
        business_id=business_id,
        conversation_id=conversation_id,
        run_id=run_id,
        current_user=user,
    )

    assert report.report_metadata.report_version == TRUST_REPORT_VERSION
    assert (
        report.report_metadata.policy_registry_version
        == TRUST_POLICY_REGISTRY_VERSION
    )
    assert report.report_metadata.scoring_version == TRUST_SCORING_VERSION
    assert report.report_metadata.grounding_version == TRUST_GROUNDING_VERSION
    assert report.grounding_report.status == GroundingStatus.GROUNDED
    assert report.evidence_chain.authoritative_tool_outputs == 1
    assert report.trust_score.score >= HIGH_TRUST_EXPECTATION
    assert report.tool_timeline[0].input_payload["api_key"] == "[REDACTED]"
    assert len(trust_events) == 1
    assert len(grounding_events) == 1


@pytest.mark.asyncio
async def test_conversation_audit_is_tenant_scoped() -> None:
    """Conversation audits reject users without an active business membership."""
    repository = FakeTrustRepository()
    business_id, user_id, conversation_id, _ = await _seed_grounded_run(repository)
    other_user = build_identity_user(uuid.uuid4())
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    service = AssistantTrustService(
        unit_of_work_factory=cast(
            Callable[[], AssistantTrustUnitOfWork],
            lambda: uow,
        ),
    )

    with pytest.raises(BusinessNotMemberException):
        await service.audit_conversation(
            business_id=business_id,
            conversation_id=conversation_id,
            current_user=other_user,
        )


@pytest.mark.asyncio
async def test_trust_tools_are_read_only() -> None:
    """Trust tools declare read-only execution metadata."""
    repository = FakeTrustRepository()
    business_id, user_id, conversation_id, run_id = await _seed_grounded_run(repository)
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    service = AssistantTrustService(
        unit_of_work_factory=cast(
            Callable[[], AssistantTrustUnitOfWork],
            lambda: uow,
        )
    )
    context = ToolContext(
        current_user=user,
        business_context=BusinessContext(
            business=business,
            membership=membership,
            user=user,
        ),
    )
    explain_tool = ExplainAssistantRunTool(service)
    audit_tool = GetAssistantConversationAuditTool(service)

    assert explain_tool.side_effect == ToolSideEffect.READ
    assert audit_tool.side_effect == ToolSideEffect.READ

    result = await explain_tool.execute(
        explain_tool.input_model(
            conversation_id=conversation_id,
            run_id=run_id,
        ),
        context,
    )

    assert result.tool_name == "assistant.explain_run"
    metadata = cast(dict[str, object], result.result["report_metadata"])
    assert metadata["report_version"] == TRUST_REPORT_VERSION


def test_assistant_trust_openapi_routes_are_registered() -> None:
    """Assistant trust endpoints are exposed in OpenAPI."""
    app = create_app(initialize_resources=False)
    openapi = app.openapi()

    assert "/api/v1/assistant/runs/{run_id}/explanation" in openapi["paths"]
    assert "/api/v1/assistant/conversations/{conversation_id}/audit" in openapi["paths"]
