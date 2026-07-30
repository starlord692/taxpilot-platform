"""Assistant conversation repositories."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.models.abstract.timestamp import utc_now
from app.common.repositories import BaseRepository
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
    EntityReferenceStatus,
    EntityResolutionConfidence,
    ExecutionMode,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
    ExecutionStepStatus,
    MessageRole,
    ToolCallStatus,
    ToolSideEffect,
)


class AssistantConversationRepository(BaseRepository[AssistantConversation]):
    """Persistence operations for assistant conversations and run audit records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async SQLAlchemy session."""
        super().__init__(session, AssistantConversation)

    async def create_conversation(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
        language: str,
        timezone: str,
    ) -> AssistantConversation:
        """Create a new conversation scoped to a business and user."""
        conversation = AssistantConversation(
            business_id=business_id,
            user_id=user_id,
            title=title,
            language=language,
            timezone=timezone,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantConversation | None:
        """Return a conversation only when it belongs to the current context."""
        statement = (
            select(AssistantConversation)
            .options(selectinload(AssistantConversation.messages))
            .where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.business_id == business_id,
                AssistantConversation.user_id == user_id,
                AssistantConversation.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update_summary(
        self,
        conversation: AssistantConversation,
        *,
        summary: str,
    ) -> AssistantConversation:
        """Update the conversation-scoped summary."""
        conversation.summary = summary
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def add_message(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AssistantMessage:
        """Persist one assistant conversation message."""
        message = AssistantMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata or {},
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 20,
    ) -> list[AssistantMessage]:
        """Return recent messages for conversation-scoped context."""
        statement = (
            select(AssistantMessage)
            .where(
                AssistantMessage.conversation_id == conversation_id,
                AssistantMessage.is_deleted.is_(False),
            )
            .order_by(AssistantMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(reversed(result.scalars().all()))

    async def create_run(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        prompt_version: str,
        provider_name: str,
        model_name: str,
    ) -> AssistantRun:
        """Create a running assistant audit record."""
        run = AssistantRun(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            status=AssistantRunStatus.RUNNING,
            prompt_version=prompt_version,
            provider_name=provider_name,
            model_name=model_name,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(
        self,
        *,
        run_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> AssistantRun | None:
        """Return one assistant run scoped to a conversation."""
        statement = select(AssistantRun).where(
            AssistantRun.id == run_id,
            AssistantRun.conversation_id == conversation_id,
            AssistantRun.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantRun]:
        """Return assistant runs for a conversation audit."""
        statement = (
            select(AssistantRun)
            .where(
                AssistantRun.conversation_id == conversation_id,
                AssistantRun.is_deleted.is_(False),
            )
            .order_by(AssistantRun.started_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
    async def complete_run(
        self,
        run: AssistantRun,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> AssistantRun:
        """Mark a run as completed."""
        run.status = AssistantRunStatus.COMPLETED
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.latency_ms = latency_ms
        run.completed_at = utc_now()
        self.session.add(run)
        await self.session.flush()
        return run

    async def fail_run(
        self,
        run: AssistantRun,
        *,
        failure_reason: str,
    ) -> AssistantRun:
        """Mark a run as failed."""
        run.status = AssistantRunStatus.FAILED
        run.failure_reason = failure_reason
        run.completed_at = utc_now()
        self.session.add(run)
        await self.session.flush()
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
        """Create a pending assistant tool-call audit record."""
        tool_call = AssistantToolCall(
            run_id=run_id,
            tool_name=tool_name,
            input_payload=input_payload,
            required_business_context=required_business_context,
            side_effect=side_effect,
            status=ToolCallStatus.PENDING,
            started_at=utc_now(),
        )
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def complete_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantToolCall:
        """Mark a tool call as completed."""
        tool_call.status = ToolCallStatus.COMPLETED
        tool_call.output_payload = output_payload
        tool_call.latency_ms = latency_ms
        tool_call.completed_at = utc_now()
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def fail_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        error_code: str,
        latency_ms: int,
    ) -> AssistantToolCall:
        """Mark a tool call as failed."""
        tool_call.status = ToolCallStatus.FAILED
        tool_call.error_code = error_code
        tool_call.latency_ms = latency_ms
        tool_call.completed_at = utc_now()
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def list_tool_calls_by_run(
        self,
        *,
        run_id: uuid.UUID,
    ) -> list[AssistantToolCall]:
        """Return all assistant tool calls for one run."""
        statement = (
            select(AssistantToolCall)
            .where(
                AssistantToolCall.run_id == run_id,
                AssistantToolCall.is_deleted.is_(False),
            )
            .order_by(AssistantToolCall.started_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
    async def list_recent_tool_calls(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 5,
    ) -> list[AssistantToolCall]:
        """Return recent completed tool calls for prompt context."""
        statement = (
            select(AssistantToolCall)
            .join(AssistantRun, AssistantToolCall.run_id == AssistantRun.id)
            .where(
                AssistantRun.conversation_id == conversation_id,
                AssistantToolCall.status == ToolCallStatus.COMPLETED,
                AssistantToolCall.is_deleted.is_(False),
            )
            .order_by(AssistantToolCall.completed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

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
        """Persist an auditable assistant context snapshot."""
        snapshot = AssistantContextSnapshot(
            conversation_id=conversation_id,
            business_id=business_id,
            user_id=user_id,
            context_version=context_version,
            context_type=context_type,
            payload=payload,
            provenance=provenance,
            expires_at=expires_at,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def list_context_snapshots(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantContextSnapshot]:
        """Return context snapshots scoped to a conversation audit."""
        statement = (
            select(AssistantContextSnapshot)
            .where(
                AssistantContextSnapshot.conversation_id == conversation_id,
                AssistantContextSnapshot.business_id == business_id,
                AssistantContextSnapshot.user_id == user_id,
                AssistantContextSnapshot.is_deleted.is_(False),
            )
            .order_by(AssistantContextSnapshot.generated_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
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
        """Persist a conversation-scoped entity reference."""
        reference = AssistantEntityReference(
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
        )
        self.session.add(reference)
        await self.session.flush()
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
        """Return active entity references for the current conversation."""
        statement = select(AssistantEntityReference).where(
            AssistantEntityReference.conversation_id == conversation_id,
            AssistantEntityReference.business_id == business_id,
            AssistantEntityReference.user_id == user_id,
            AssistantEntityReference.status == EntityReferenceStatus.ACTIVE,
            AssistantEntityReference.expires_at > now,
            AssistantEntityReference.is_deleted.is_(False),
        )
        if entity_type is not None:
            statement = statement.where(
                AssistantEntityReference.entity_type == entity_type,
            )
        statement = statement.order_by(AssistantEntityReference.last_seen_at.desc())
        result = await self.session.execute(statement.limit(limit))
        return list(result.scalars().all())

    async def get_active_workflow(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
    ) -> AssistantWorkflow | None:
        """Return the active non-expired workflow for a conversation."""
        statement = (
            select(AssistantWorkflow)
            .where(
                AssistantWorkflow.conversation_id == conversation_id,
                AssistantWorkflow.business_id == business_id,
                AssistantWorkflow.user_id == user_id,
                AssistantWorkflow.status.in_(
                    [
                        AssistantWorkflowStatus.ACTIVE,
                        AssistantWorkflowStatus.WAITING_FOR_USER,
                        AssistantWorkflowStatus.EXECUTING_TOOLS,
                        AssistantWorkflowStatus.READY_FOR_ACTION,
                    ]
                ),
                AssistantWorkflow.expires_at > now,
                AssistantWorkflow.is_deleted.is_(False),
            )
            .order_by(AssistantWorkflow.last_transition_at.desc())
        )
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none()

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
        """Create assistant workflow tracking state."""
        workflow = AssistantWorkflow(
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
        )
        self.session.add(workflow)
        await self.session.flush()
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
        """Update assistant workflow tracking state."""
        workflow.status = status
        workflow.current_step = current_step
        workflow.active_entity_refs = active_entity_refs
        workflow.pending_decisions = pending_decisions
        workflow.provenance = provenance
        workflow.expires_at = expires_at
        workflow.last_transition_at = utc_now()
        self.session.add(workflow)
        await self.session.flush()
        return workflow

    async def get_completed_execution_plan_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantExecutionPlan | None:
        """Return a completed execution plan for idempotent replay."""
        statement = (
            select(AssistantExecutionPlan)
            .options(selectinload(AssistantExecutionPlan.steps))
            .where(
                AssistantExecutionPlan.business_id == business_id,
                AssistantExecutionPlan.idempotency_key == idempotency_key,
                AssistantExecutionPlan.status == ExecutionPlanStatus.COMPLETED,
                AssistantExecutionPlan.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

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
        """Persist an assistant execution plan audit record."""
        plan = AssistantExecutionPlan(
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
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def get_execution_plan_by_run(
        self,
        *,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> AssistantExecutionPlan | None:
        """Return the execution plan for one run."""
        statement = (
            select(AssistantExecutionPlan)
            .options(
                selectinload(AssistantExecutionPlan.steps),
                selectinload(AssistantExecutionPlan.approvals),
            )
            .where(
                AssistantExecutionPlan.run_id == run_id,
                AssistantExecutionPlan.business_id == business_id,
                AssistantExecutionPlan.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_execution_plans_by_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantExecutionPlan]:
        """Return execution plans for a conversation audit."""
        statement = (
            select(AssistantExecutionPlan)
            .options(
                selectinload(AssistantExecutionPlan.steps),
                selectinload(AssistantExecutionPlan.approvals),
            )
            .where(
                AssistantExecutionPlan.conversation_id == conversation_id,
                AssistantExecutionPlan.business_id == business_id,
                AssistantExecutionPlan.is_deleted.is_(False),
            )
            .order_by(AssistantExecutionPlan.started_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
    async def update_execution_plan_status(
        self,
        plan: AssistantExecutionPlan,
        *,
        status: ExecutionPlanStatus,
        failure_reason: str | None = None,
    ) -> AssistantExecutionPlan:
        """Update execution plan lifecycle state."""
        plan.status = status
        plan.failure_reason = failure_reason
        if status in {
            ExecutionPlanStatus.COMPLETED,
            ExecutionPlanStatus.FAILED,
            ExecutionPlanStatus.BLOCKED,
        }:
            plan.completed_at = utc_now()
        self.session.add(plan)
        await self.session.flush()
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
        """Persist a pending execution step audit record."""
        step = AssistantExecutionStep(
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
        )
        self.session.add(step)
        await self.session.flush()
        return step

    async def mark_execution_step_running(
        self,
        step: AssistantExecutionStep,
    ) -> AssistantExecutionStep:
        """Mark an execution step as running."""
        step.status = ExecutionStepStatus.RUNNING
        step.started_at = utc_now()
        self.session.add(step)
        await self.session.flush()
        return step

    async def complete_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        tool_call_id: uuid.UUID,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantExecutionStep:
        """Mark an execution step as completed."""
        step.status = ExecutionStepStatus.COMPLETED
        step.tool_call_id = tool_call_id
        step.output_payload = output_payload
        step.latency_ms = latency_ms
        step.completed_at = utc_now()
        self.session.add(step)
        await self.session.flush()
        return step

    async def fail_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        error_code: str,
        failure_reason: str,
        latency_ms: int | None = None,
    ) -> AssistantExecutionStep:
        """Mark an execution step as failed."""
        step.status = ExecutionStepStatus.FAILED
        step.error_code = error_code
        step.failure_reason = failure_reason
        step.latency_ms = latency_ms
        step.completed_at = utc_now()
        self.session.add(step)
        await self.session.flush()
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
        """Persist an assistant approval checkpoint."""
        approval = AssistantApproval(
            plan_id=plan_id,
            business_id=business_id,
            requested_by=requested_by,
            approval_level=approval_level,
            status=status,
            reason=reason,
            plan_hash=plan_hash,
            provenance=provenance,
            expires_at=expires_at,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

