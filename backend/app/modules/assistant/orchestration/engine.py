"""Deterministic assistant execution engine."""

import time
import uuid
from datetime import datetime
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from app.common.events import Event, EventDispatcher
from app.modules.assistant.approvals import ApprovalCheckpointService
from app.modules.assistant.events import (
    AssistantApprovalCheckpointCreatedEvent,
    AssistantExecutionCompletedEvent,
    AssistantExecutionFailedEvent,
    AssistantExecutionPlanCreatedEvent,
    AssistantExecutionPolicyEvaluatedEvent,
)
from app.modules.assistant.models import (
    ApprovalLevel,
    ApprovalStatus,
    AssistantApproval,
    AssistantExecutionPlan,
    AssistantExecutionStep,
    AssistantToolCall,
    ExecutionMode,
    ExecutionPlanStatus,
    ExecutionPolicyDecision,
    ToolSideEffect,
)
from app.modules.assistant.planning import ExecutionPlan
from app.modules.assistant.policies import ExecutionPolicyEvaluator
from app.modules.assistant.provenance import ExecutionProvenanceBuilder
from app.modules.assistant.tools import AssistantToolExecutor, ToolContext


class AssistantExecutionRepository(Protocol):
    """Repository behavior required by the execution engine."""

    async def get_completed_execution_plan_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantExecutionPlan | None:
        """Return a completed plan for idempotent replay."""
        ...

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
        """Persist an execution plan."""
        ...

    async def update_execution_plan_status(
        self,
        plan: AssistantExecutionPlan,
        *,
        status: ExecutionPlanStatus,
        failure_reason: str | None = None,
    ) -> AssistantExecutionPlan:
        """Update execution plan status."""
        ...

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
        """Persist an execution step."""
        ...

    async def mark_execution_step_running(
        self,
        step: AssistantExecutionStep,
    ) -> AssistantExecutionStep:
        """Mark a step as running."""
        ...

    async def complete_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        tool_call_id: uuid.UUID,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantExecutionStep:
        """Mark a step as completed."""
        ...

    async def fail_execution_step(
        self,
        step: AssistantExecutionStep,
        *,
        error_code: str,
        failure_reason: str,
        latency_ms: int | None = None,
    ) -> AssistantExecutionStep:
        """Mark a step as failed."""
        ...

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
        """Persist an approval checkpoint."""
        ...

    async def create_tool_call(
        self,
        *,
        run_id: uuid.UUID,
        tool_name: str,
        input_payload: dict[str, object],
        required_business_context: bool,
        side_effect: ToolSideEffect,
    ) -> AssistantToolCall:
        """Create a tool call audit record."""
        ...

    async def complete_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantToolCall:
        """Complete a tool call audit record."""
        ...

    async def fail_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        error_code: str,
        latency_ms: int,
    ) -> AssistantToolCall:
        """Fail a tool call audit record."""
        ...


class ExecutionEngineResult(BaseModel):
    """Result returned after assistant plan execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_outputs: list[dict[str, object]] = Field(default_factory=list)
    tool_calls: list[AssistantToolCall] = Field(default_factory=list)
    approval_required: bool = False


class AssistantExecutionEngine:
    """Validate policy and execute plans through registered assistant tools."""

    def __init__(
        self,
        *,
        tool_executor: AssistantToolExecutor,
        policy_evaluator: ExecutionPolicyEvaluator | None = None,
        approval_service: ApprovalCheckpointService | None = None,
        provenance_builder: ExecutionProvenanceBuilder | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        """Initialize deterministic orchestration dependencies."""
        self._tool_executor = tool_executor
        self._policy_evaluator = policy_evaluator or ExecutionPolicyEvaluator()
        self._approval_service = approval_service or ApprovalCheckpointService()
        self._provenance_builder = provenance_builder or ExecutionProvenanceBuilder()
        self._event_dispatcher = event_dispatcher

    async def execute_plan(
        self,
        *,
        repository: AssistantExecutionRepository,
        plan: ExecutionPlan,
        tool_context: ToolContext,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ExecutionEngineResult:
        """Persist, validate, and execute one normalized assistant plan."""
        existing = await repository.get_completed_execution_plan_by_idempotency(
            business_id=business_id,
            idempotency_key=plan.idempotency_key,
        )
        if existing is not None:
            outputs = [
                step.output_payload
                for step in existing.steps
                if step.output_payload is not None
            ]
            return ExecutionEngineResult(tool_outputs=outputs)

        policy_result = self._policy_evaluator.evaluate(plan)
        correlation_id = str(uuid.uuid4())
        plan_record = await repository.create_execution_plan(
            conversation_id=conversation_id,
            run_id=run_id,
            business_id=business_id,
            user_id=user_id,
            plan_version=plan.plan_version,
            planner_version=plan.planner_version,
            normalization_version=plan.normalization_version,
            prompt_version=plan.prompt_version,
            context_version=plan.context_version,
            status=ExecutionPlanStatus.PLANNED,
            execution_mode=plan.execution_mode,
            policy_decision=policy_result.decision,
            approval_level=policy_result.approval_level,
            approval_status=self._approval_status(policy_result.approval_level),
            idempotency_key=plan.idempotency_key,
            normalized_plan=plan.model_dump(mode="json"),
            policy_reasons=list(policy_result.reasons),
            provenance=self._provenance_builder.for_plan(
                plan=plan,
                business_id=str(business_id),
                user_id=str(user_id),
                conversation_id=str(conversation_id),
                run_id=str(run_id),
                correlation_id=correlation_id,
            ),
            correlation_id=correlation_id,
        )
        await self._dispatch(
            AssistantExecutionPlanCreatedEvent(
                plan_id=plan_record.id,
                run_id=run_id,
                business_id=business_id,
                plan_version=plan.plan_version,
            )
        )
        await self._dispatch(
            AssistantExecutionPolicyEvaluatedEvent(
                plan_id=plan_record.id,
                run_id=run_id,
                business_id=business_id,
                decision=policy_result.decision.value,
            )
        )
        steps = await self._persist_steps(
            repository=repository,
            plan_record=plan_record,
            plan=plan,
            business_id=business_id,
            run_id=run_id,
            correlation_id=correlation_id,
        )
        if policy_result.decision == ExecutionPolicyDecision.BLOCKED:
            await repository.update_execution_plan_status(
                plan_record,
                status=ExecutionPlanStatus.BLOCKED,
                failure_reason="; ".join(policy_result.reasons),
            )
            return ExecutionEngineResult()
        if policy_result.decision == ExecutionPolicyDecision.REQUIRES_APPROVAL:
            checkpoint = self._approval_service.build_checkpoint(
                plan=plan,
                policy_result=policy_result,
                business_id=str(business_id),
                requested_by=str(user_id),
            )
            if checkpoint is not None:
                approval_level = cast(ApprovalLevel, checkpoint["approval_level"])
                await repository.create_approval_checkpoint(
                    plan_id=plan_record.id,
                    business_id=business_id,
                    requested_by=user_id,
                    approval_level=approval_level,
                    status=cast(ApprovalStatus, checkpoint["status"]),
                    reason=str(checkpoint["reason"]),
                    plan_hash=str(checkpoint["plan_hash"]),
                    provenance=cast(dict[str, object], checkpoint["provenance"]),
                    expires_at=cast(datetime, checkpoint["expires_at"]),
                )
                await self._dispatch(
                    AssistantApprovalCheckpointCreatedEvent(
                        plan_id=plan_record.id,
                        business_id=business_id,
                        approval_level=approval_level.value,
                    )
                )
            await repository.update_execution_plan_status(
                plan_record,
                status=ExecutionPlanStatus.APPROVAL_REQUIRED,
            )
            return ExecutionEngineResult(approval_required=True)
        await repository.update_execution_plan_status(
            plan_record,
            status=ExecutionPlanStatus.EXECUTING,
        )
        return await self._execute_steps(
            repository=repository,
            plan_record=plan_record,
            plan=plan,
            steps=steps,
            tool_context=tool_context,
            run_id=run_id,
        )

    async def _persist_steps(
        self,
        *,
        repository: AssistantExecutionRepository,
        plan_record: AssistantExecutionPlan,
        plan: ExecutionPlan,
        business_id: uuid.UUID,
        run_id: uuid.UUID,
        correlation_id: str,
    ) -> list[AssistantExecutionStep]:
        """Persist pending audit rows for every plan step."""
        records: list[AssistantExecutionStep] = []
        for step in plan.steps:
            record = await repository.create_execution_step(
                plan_id=plan_record.id,
                step_order=step.step_order,
                tool_name=step.tool_name,
                capability_name=step.manifest.capability_name,
                tool_manifest_version=step.manifest.manifest_version,
                input_payload=step.arguments,
                required_business_context=step.manifest.requires_business_context,
                side_effect=step.manifest.side_effect,
                idempotency_key=step.idempotency_key,
                dependencies=list(step.dependencies),
                provenance=self._provenance_builder.for_step(
                    plan=plan,
                    step=step,
                    business_id=str(business_id),
                    run_id=str(run_id),
                    correlation_id=correlation_id,
                ),
            )
            records.append(record)
        return records

    async def _execute_steps(
        self,
        *,
        repository: AssistantExecutionRepository,
        plan_record: AssistantExecutionPlan,
        plan: ExecutionPlan,
        steps: list[AssistantExecutionStep],
        tool_context: ToolContext,
        run_id: uuid.UUID,
    ) -> ExecutionEngineResult:
        """Execute persisted steps sequentially through the tool executor."""
        outputs: list[dict[str, object]] = []
        tool_calls: list[AssistantToolCall] = []
        for plan_step, step_record in zip(plan.steps, steps, strict=True):
            started = time.perf_counter()
            await repository.mark_execution_step_running(step_record)
            tool_call = await repository.create_tool_call(
                run_id=run_id,
                tool_name=plan_step.tool_name,
                input_payload=plan_step.arguments,
                required_business_context=plan_step.manifest.requires_business_context,
                side_effect=plan_step.manifest.side_effect,
            )
            try:
                result = await self._tool_executor.execute(
                    tool_name=plan_step.tool_name,
                    arguments=plan_step.arguments,
                    context=tool_context,
                    allow_write_tools=(
                        plan_step.manifest.side_effect == ToolSideEffect.WRITE
                    ),
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                await repository.fail_tool_call(
                    tool_call,
                    error_code=type(exc).__name__,
                    latency_ms=latency_ms,
                )
                await repository.fail_execution_step(
                    step_record,
                    error_code=type(exc).__name__,
                    failure_reason=str(exc),
                    latency_ms=latency_ms,
                )
                await repository.update_execution_plan_status(
                    plan_record,
                    status=ExecutionPlanStatus.FAILED,
                    failure_reason=str(exc),
                )
                await self._dispatch(
                    AssistantExecutionFailedEvent(
                        plan_id=plan_record.id,
                        run_id=run_id,
                        business_id=tool_context.business_context.business_id
                        if tool_context.business_context is not None
                        else uuid.UUID(int=0),
                        error_code=type(exc).__name__,
                    )
                )
                raise
            output_payload = result.model_dump()
            latency_ms = int((time.perf_counter() - started) * 1000)
            audited_tool_call = await repository.complete_tool_call(
                tool_call,
                output_payload=output_payload,
                latency_ms=latency_ms,
            )
            await repository.complete_execution_step(
                step_record,
                tool_call_id=audited_tool_call.id,
                output_payload=output_payload,
                latency_ms=latency_ms,
            )
            outputs.append(output_payload)
            tool_calls.append(audited_tool_call)
        await repository.update_execution_plan_status(
            plan_record,
            status=ExecutionPlanStatus.COMPLETED,
        )
        await self._dispatch(
            AssistantExecutionCompletedEvent(
                plan_id=plan_record.id,
                run_id=run_id,
                business_id=tool_context.business_context.business_id
                if tool_context.business_context is not None
                else uuid.UUID(int=0),
            )
        )
        return ExecutionEngineResult(tool_outputs=outputs, tool_calls=tool_calls)

    def _approval_status(self, approval_level: ApprovalLevel) -> ApprovalStatus:
        """Return initial approval status for a policy result."""
        if approval_level in {ApprovalLevel.NONE, ApprovalLevel.AUTO_ALLOWED}:
            return ApprovalStatus.NOT_REQUIRED
        return ApprovalStatus.PENDING

    async def _dispatch(self, event: Event) -> None:
        """Dispatch an orchestration event when a dispatcher is configured."""
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch(event)




