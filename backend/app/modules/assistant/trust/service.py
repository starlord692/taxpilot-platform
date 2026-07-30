"""Read-only assistant trust and audit service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.events import (
    AssistantGroundingVerifiedEvent,
    AssistantTrustReportGeneratedEvent,
)
from app.modules.assistant.models import (
    ApprovalStatus,
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantExecutionPlan,
    AssistantMessage,
    AssistantRun,
    AssistantRunStatus,
    AssistantToolCall,
    ExecutionPolicyDecision,
    ToolSideEffect,
)
from app.modules.assistant.trust.evidence import AssistantEvidenceChainBuilder
from app.modules.assistant.trust.exceptions import AssistantRunNotFoundException
from app.modules.assistant.trust.grounding import AssistantGroundingVerifier
from app.modules.assistant.trust.policies import TrustPolicyRegistry
from app.modules.assistant.trust.schemas import (
    AssistantApprovalTrace,
    AssistantAuditTimelineEntry,
    AssistantConversationAudit,
    AssistantEvidenceChain,
    AssistantExecutionStepTrace,
    AssistantGroundingReport,
    AssistantPolicyTrace,
    AssistantRunExplanation,
    AssistantToolExecutionTrace,
    AuditTimelineEventType,
    TrustPolicyResult,
    TrustPolicyStatus,
    TrustReportVersion,
)
from app.modules.assistant.trust.scoring import AssistantTrustScorer
from app.modules.business.api.context import (
    BusinessContextBusinessRepository,
    BusinessContextMembershipRepository,
    resolve_business_context,
)
from app.modules.identity.models import IdentityUser

SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "password_hash",
    "secret",
    "api_key",
}


class AssistantTrustRepository(Protocol):
    """Read behavior required for assistant trust reporting."""

    async def get_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantConversation | None:
        """Return a scoped conversation."""
        ...

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 20,
    ) -> list[AssistantMessage]:
        """Return conversation messages."""
        ...

    async def get_run(
        self,
        *,
        run_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> AssistantRun | None:
        """Return one assistant run."""
        ...

    async def list_runs(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantRun]:
        """Return runs for a conversation."""
        ...

    async def list_tool_calls_by_run(
        self,
        *,
        run_id: uuid.UUID,
    ) -> list[AssistantToolCall]:
        """Return tool calls for one run."""
        ...

    async def get_execution_plan_by_run(
        self,
        *,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> AssistantExecutionPlan | None:
        """Return the execution plan for one run."""
        ...

    async def list_execution_plans_by_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantExecutionPlan]:
        """Return execution plans for a conversation."""
        ...

    async def list_context_snapshots(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AssistantContextSnapshot]:
        """Return scoped context snapshots."""
        ...


class AssistantTrustUnitOfWork(Protocol):
    """Unit of Work contract for read-only assistant trust reports."""

    businesses: BusinessContextBusinessRepository
    business_memberships: BusinessContextMembershipRepository
    assistant_conversations: AssistantTrustRepository

    async def __aenter__(self) -> "AssistantTrustUnitOfWork":
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


AssistantTrustUnitOfWorkFactory = Callable[[], AssistantTrustUnitOfWork]


class AssistantTrustService:
    """Build read-only assistant trust, explanation, and audit reports."""

    def __init__(
        self,
        *,
        unit_of_work_factory: AssistantTrustUnitOfWorkFactory,
        event_dispatcher: EventDispatcher | None = None,
        policy_registry: TrustPolicyRegistry | None = None,
        evidence_builder: AssistantEvidenceChainBuilder | None = None,
        grounding_verifier: AssistantGroundingVerifier | None = None,
        scorer: AssistantTrustScorer | None = None,
    ) -> None:
        """Initialize deterministic trust reporting dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._policy_registry = policy_registry or TrustPolicyRegistry()
        self._evidence_builder = evidence_builder or AssistantEvidenceChainBuilder()
        self._grounding_verifier = grounding_verifier or AssistantGroundingVerifier()
        self._scorer = scorer or AssistantTrustScorer()

    async def explain_run(
        self,
        *,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        current_user: IdentityUser,
    ) -> AssistantRunExplanation:
        """Return a read-only explanation for one assistant run."""
        async with self._unit_of_work_factory() as uow:
            context = await resolve_business_context(
                uow,
                business_id=business_id,
                current_user=current_user,
                entered=True,
            )
            conversation = await uow.assistant_conversations.get_conversation(
                conversation_id=conversation_id,
                business_id=context.business_id,
                user_id=context.user_id,
            )
            if conversation is None:
                raise AssistantRunNotFoundException(
                    "Assistant run not found",
                    details={"conversation_id": str(conversation_id)},
                )
            run = await uow.assistant_conversations.get_run(
                run_id=run_id,
                conversation_id=conversation.id,
            )
            if run is None:
                raise AssistantRunNotFoundException(
                    "Assistant run not found",
                    details={"run_id": str(run_id)},
                )
            tool_calls = await uow.assistant_conversations.list_tool_calls_by_run(
                run_id=run.id,
            )
            plan = await uow.assistant_conversations.get_execution_plan_by_run(
                run_id=run.id,
                business_id=context.business_id,
            )
            evidence_chain = self._evidence_builder.build(tool_calls)
            grounding = self._grounding_verifier.verify(
                run_status=run.status,
                tool_calls=tool_calls,
                evidence_chain=evidence_chain,
            )
            policy_results = self._evaluate_run_policies(
                run=run,
                plan=plan,
                tool_calls=tool_calls,
                evidence_chain=evidence_chain,
                grounding=grounding,
            )
            trust_score = self._scorer.score(policy_results)
            await self._dispatch_trust_events(
                conversation_id=conversation.id,
                run_id=run.id,
                business_id=context.business_id,
                trust_score=trust_score.score,
                grounding_status=grounding.status.value,
            )
            return AssistantRunExplanation(
                report_metadata=TrustReportVersion(),
                business_id=context.business_id,
                user_id=context.user_id,
                conversation_id=conversation.id,
                run_id=run.id,
                generated_at=utc_now(),
                run_status=run.status.value,
                prompt_version=run.prompt_version,
                provider_name=run.provider_name,
                model_name=run.model_name,
                policy_trace=self._policy_trace(plan),
                approval_traces=self._approval_traces(plan),
                tool_timeline=self._tool_traces(tool_calls),
                execution_steps=self._step_traces(plan),
                evidence_chain=evidence_chain,
                grounding_report=grounding,
                policy_results=policy_results,
                trust_score=trust_score,
            )

    async def audit_conversation(
        self,
        *,
        business_id: uuid.UUID,
        conversation_id: uuid.UUID,
        current_user: IdentityUser,
    ) -> AssistantConversationAudit:
        """Return a chronological read-only audit for one conversation."""
        async with self._unit_of_work_factory() as uow:
            context = await resolve_business_context(
                uow,
                business_id=business_id,
                current_user=current_user,
                entered=True,
            )
            conversation = await uow.assistant_conversations.get_conversation(
                conversation_id=conversation_id,
                business_id=context.business_id,
                user_id=context.user_id,
            )
            if conversation is None:
                raise AssistantRunNotFoundException(
                    "Assistant conversation not found",
                    details={"conversation_id": str(conversation_id)},
                )
            messages = await uow.assistant_conversations.list_messages(
                conversation_id=conversation.id,
                limit=100,
            )
            runs = await uow.assistant_conversations.list_runs(
                conversation_id=conversation.id,
                limit=100,
            )
            plans = (
                await uow.assistant_conversations.list_execution_plans_by_conversation(
                    conversation_id=conversation.id,
                    business_id=context.business_id,
                    limit=100,
                )
            )
            snapshots = await uow.assistant_conversations.list_context_snapshots(
                conversation_id=conversation.id,
                business_id=context.business_id,
                user_id=context.user_id,
                limit=100,
            )
            tool_calls: list[AssistantToolCall] = []
            for run in runs:
                tool_calls.extend(
                    await uow.assistant_conversations.list_tool_calls_by_run(
                        run_id=run.id,
                    )
                )
            timeline = self._conversation_timeline(
                messages=messages,
                runs=runs,
                plans=plans,
                tool_calls=tool_calls,
                snapshots=snapshots,
            )
            policy_results = [
                self._policy_result(
                    "business_context_resolved",
                    TrustPolicyStatus.PASS,
                    "Business context was resolved before audit generation.",
                ),
                self._policy_result(
                    "tenant_scope_consistent",
                    TrustPolicyStatus.PASS,
                    "Conversation audit is scoped to the authenticated business.",
                ),
            ]
            trust_score = self._scorer.score(policy_results)
            await self._dispatch_trust_report_event(
                conversation_id=conversation.id,
                run_id=None,
                business_id=context.business_id,
                trust_score=trust_score.score,
            )
            return AssistantConversationAudit(
                report_metadata=TrustReportVersion(),
                business_id=context.business_id,
                user_id=context.user_id,
                conversation_id=conversation.id,
                generated_at=utc_now(),
                timeline=timeline,
                run_count=len(runs),
                tool_call_count=len(tool_calls),
                failed_run_count=sum(
                    run.status == AssistantRunStatus.FAILED for run in runs
                ),
                trust_score=trust_score,
            )

    def _evaluate_run_policies(
        self,
        *,
        run: AssistantRun,
        plan: AssistantExecutionPlan | None,
        tool_calls: list[AssistantToolCall],
        evidence_chain: AssistantEvidenceChain,
        grounding: AssistantGroundingReport,
    ) -> list[TrustPolicyResult]:
        """Evaluate structural trust policies for a run."""
        results = [
            self._policy_result(
                "business_context_resolved",
                TrustPolicyStatus.PASS,
                "Business context was resolved before report generation.",
            ),
            self._policy_result(
                "tenant_scope_consistent",
                TrustPolicyStatus.PASS,
                "Run belongs to the requested conversation and business context.",
            ),
            self._policy_result(
                "prompt_version_recorded",
                TrustPolicyStatus.PASS
                if run.prompt_version
                else TrustPolicyStatus.FAIL,
                "Prompt version is recorded."
                if run.prompt_version
                else "Prompt version is missing.",
            ),
            self._policy_result(
                "tool_outputs_required_for_business_facts",
                TrustPolicyStatus.PASS
                if evidence_chain.authoritative_tool_outputs > 0
                else TrustPolicyStatus.WARNING,
                "Completed authoritative tool output is available."
                if evidence_chain.authoritative_tool_outputs > 0
                else "No completed tool output is available for this run.",
            ),
            self._policy_result(
                "failed_run_has_failure_reason",
                TrustPolicyStatus.NOT_APPLICABLE
                if run.status != AssistantRunStatus.FAILED
                else (
                    TrustPolicyStatus.PASS
                    if run.failure_reason
                    else TrustPolicyStatus.WARNING
                ),
                "Run did not fail."
                if run.status != AssistantRunStatus.FAILED
                else (
                    "Failure reason is recorded."
                    if run.failure_reason
                    else "Run failed without a failure reason."
                ),
            ),
        ]
        results.extend(self._tool_policy_results(tool_calls))
        results.extend(self._plan_policy_results(plan))
        if grounding.evidence_count > 0:
            results.append(
                self._policy_result(
                    "evidence_required_for_insights",
                    TrustPolicyStatus.PASS,
                    "Evidence references are present when insight output exists.",
                )
            )
            results.append(
                self._policy_result(
                    "confidence_score_present",
                    self._confidence_policy_status(tool_calls),
                    "Insight confidence was checked in completed outputs.",
                )
            )
        return results

    def _tool_policy_results(
        self,
        tool_calls: list[AssistantToolCall],
    ) -> list[TrustPolicyResult]:
        """Evaluate tool boundary policies."""
        if not tool_calls:
            return []
        all_contextual = all(call.required_business_context for call in tool_calls)
        all_read = all(call.side_effect == ToolSideEffect.READ for call in tool_calls)
        return [
            self._policy_result(
                "business_context_required",
                TrustPolicyStatus.PASS if all_contextual else TrustPolicyStatus.FAIL,
                "All recorded tools required business context."
                if all_contextual
                else "At least one tool did not require business context.",
            ),
            self._policy_result(
                "read_only_tool_respected",
                TrustPolicyStatus.PASS if all_read else TrustPolicyStatus.FAIL,
                "All recorded tools were read-only."
                if all_read
                else "At least one recorded tool declared write side effects.",
            ),
        ]

    def _plan_policy_results(
        self,
        plan: AssistantExecutionPlan | None,
    ) -> list[TrustPolicyResult]:
        """Evaluate execution plan policies."""
        if plan is None:
            return [
                self._policy_result(
                    "execution_plan_version_recorded",
                    TrustPolicyStatus.WARNING,
                    "No execution plan was recorded for this run.",
                )
            ]
        requires_approval = (
            plan.policy_decision == ExecutionPolicyDecision.REQUIRES_APPROVAL
        )
        approval_recorded = bool(plan.approvals)
        return [
            self._policy_result(
                "execution_plan_version_recorded",
                TrustPolicyStatus.PASS
                if plan.plan_version and plan.planner_version
                else TrustPolicyStatus.WARNING,
                "Execution plan version metadata is recorded."
                if plan.plan_version and plan.planner_version
                else "Execution plan version metadata is incomplete.",
            ),
            self._policy_result(
                "tool_manifest_version_recorded",
                TrustPolicyStatus.PASS
                if all(step.tool_manifest_version for step in plan.steps)
                else TrustPolicyStatus.WARNING,
                "Execution step manifest versions are recorded."
                if all(step.tool_manifest_version for step in plan.steps)
                else "At least one execution step lacks manifest version metadata.",
            ),
            self._policy_result(
                "write_tool_requires_policy_approval",
                TrustPolicyStatus.PASS
                if plan.approval_status
                in {ApprovalStatus.NOT_REQUIRED, ApprovalStatus.PENDING}
                else TrustPolicyStatus.WARNING,
                "Execution policy recorded approval status.",
            ),
            self._policy_result(
                "approval_checkpoint_recorded_when_required",
                TrustPolicyStatus.NOT_APPLICABLE
                if not requires_approval
                else (
                    TrustPolicyStatus.PASS
                    if approval_recorded
                    else TrustPolicyStatus.FAIL
                ),
                "Approval was not required."
                if not requires_approval
                else (
                    "Approval checkpoint was recorded."
                    if approval_recorded
                    else "Approval was required but no checkpoint was recorded."
                ),
            ),
        ]

    def _confidence_policy_status(
        self,
        tool_calls: list[AssistantToolCall],
    ) -> TrustPolicyStatus:
        """Return whether completed insight outputs include confidence."""
        for tool_call in tool_calls:
            result = (tool_call.output_payload or {}).get("result")
            if isinstance(result, dict) and "confidence" in result:
                return TrustPolicyStatus.PASS
        return TrustPolicyStatus.WARNING

    def _policy_result(
        self,
        key: str,
        status: TrustPolicyStatus,
        details: str,
    ) -> TrustPolicyResult:
        """Build one evaluated trust policy result."""
        return TrustPolicyResult(
            policy=self._policy_registry.get(key),
            status=status,
            details=details,
        )

    def _policy_trace(
        self,
        plan: AssistantExecutionPlan | None,
    ) -> AssistantPolicyTrace:
        """Return execution policy trace for a run."""
        if plan is None:
            return AssistantPolicyTrace()
        return AssistantPolicyTrace(
            plan_id=plan.id,
            policy_decision=plan.policy_decision.value,
            approval_level=plan.approval_level.value,
            approval_status=plan.approval_status.value,
            policy_reasons=plan.policy_reasons,
            execution_mode=plan.execution_mode.value,
            idempotency_key=plan.idempotency_key,
            correlation_id=plan.correlation_id,
        )

    def _approval_traces(
        self,
        plan: AssistantExecutionPlan | None,
    ) -> list[AssistantApprovalTrace]:
        """Return approval traces for an execution plan."""
        if plan is None:
            return []
        return [
            AssistantApprovalTrace(
                approval_id=approval.id,
                plan_id=approval.plan_id,
                approval_level=approval.approval_level.value,
                status=approval.status.value,
                reason=approval.reason,
                requested_by=approval.requested_by,
                approved_by=approval.approved_by,
                expires_at=approval.expires_at,
                decided_at=approval.decided_at,
            )
            for approval in plan.approvals
        ]

    def _tool_traces(
        self,
        tool_calls: list[AssistantToolCall],
    ) -> list[AssistantToolExecutionTrace]:
        """Return redacted tool execution traces."""
        return [
            AssistantToolExecutionTrace(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                status=tool_call.status.value,
                side_effect=tool_call.side_effect.value,
                required_business_context=tool_call.required_business_context,
                input_payload=self._redact(tool_call.input_payload),
                output_payload=self._redact(tool_call.output_payload)
                if tool_call.output_payload is not None
                else None,
                latency_ms=tool_call.latency_ms,
                error_code=tool_call.error_code,
                started_at=tool_call.started_at,
                completed_at=tool_call.completed_at,
            )
            for tool_call in tool_calls
        ]

    def _step_traces(
        self,
        plan: AssistantExecutionPlan | None,
    ) -> list[AssistantExecutionStepTrace]:
        """Return execution step traces."""
        if plan is None:
            return []
        return [
            AssistantExecutionStepTrace(
                step_id=step.id,
                step_order=step.step_order,
                tool_name=step.tool_name,
                capability_name=step.capability_name,
                tool_manifest_version=step.tool_manifest_version,
                status=step.status.value,
                side_effect=step.side_effect.value,
                required_business_context=step.required_business_context,
                idempotency_key=step.idempotency_key,
                latency_ms=step.latency_ms,
                error_code=step.error_code,
                failure_reason=step.failure_reason,
            )
            for step in sorted(plan.steps, key=lambda item: item.step_order)
        ]

    def _conversation_timeline(
        self,
        *,
        messages: list[AssistantMessage],
        runs: list[AssistantRun],
        plans: list[AssistantExecutionPlan],
        tool_calls: list[AssistantToolCall],
        snapshots: list[AssistantContextSnapshot],
    ) -> list[AssistantAuditTimelineEntry]:
        """Build a chronological conversation audit timeline."""
        timeline: list[AssistantAuditTimelineEntry] = []
        for message in messages:
            timeline.append(
                AssistantAuditTimelineEntry(
                    occurred_at=message.created_at,
                    event_type=AuditTimelineEventType.MESSAGE,
                    label=f"{message.role.value} message",
                    reference_id=message.id,
                    status=message.role.value,
                    details={"role": message.role.value},
                )
            )
        for run in runs:
            timeline.append(
                AssistantAuditTimelineEntry(
                    occurred_at=run.started_at,
                    event_type=AuditTimelineEventType.RUN,
                    label="assistant run",
                    reference_id=run.id,
                    status=run.status.value,
                    details={"prompt_version": run.prompt_version},
                )
            )
        for plan in plans:
            timeline.append(
                AssistantAuditTimelineEntry(
                    occurred_at=plan.started_at,
                    event_type=AuditTimelineEventType.EXECUTION_PLAN,
                    label="execution plan",
                    reference_id=plan.id,
                    status=plan.status.value,
                    details={"policy_decision": plan.policy_decision.value},
                )
            )
            for approval in plan.approvals:
                timeline.append(
                    AssistantAuditTimelineEntry(
                        occurred_at=approval.created_at,
                        event_type=AuditTimelineEventType.APPROVAL,
                        label="approval checkpoint",
                        reference_id=approval.id,
                        status=approval.status.value,
                        details={"approval_level": approval.approval_level.value},
                    )
                )
        for tool_call in tool_calls:
            timeline.append(
                AssistantAuditTimelineEntry(
                    occurred_at=tool_call.started_at or tool_call.created_at,
                    event_type=AuditTimelineEventType.TOOL_CALL,
                    label=tool_call.tool_name,
                    reference_id=tool_call.id,
                    status=tool_call.status.value,
                    details={"side_effect": tool_call.side_effect.value},
                )
            )
        for snapshot in snapshots:
            timeline.append(
                AssistantAuditTimelineEntry(
                    occurred_at=snapshot.generated_at,
                    event_type=AuditTimelineEventType.CONTEXT,
                    label="context snapshot",
                    reference_id=snapshot.id,
                    status=snapshot.context_type.value,
                    details={"context_version": snapshot.context_version},
                )
            )
        return sorted(timeline, key=lambda entry: entry.occurred_at)

    async def _dispatch_trust_events(
        self,
        *,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        business_id: uuid.UUID,
        trust_score: float,
        grounding_status: str,
    ) -> None:
        """Dispatch observational trust and grounding events."""
        await self._dispatch_trust_report_event(
            conversation_id=conversation_id,
            run_id=run_id,
            business_id=business_id,
            trust_score=trust_score,
        )
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch(
                AssistantGroundingVerifiedEvent(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    business_id=business_id,
                    status=grounding_status,
                )
            )

    async def _dispatch_trust_report_event(
        self,
        *,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID | None,
        business_id: uuid.UUID,
        trust_score: float,
    ) -> None:
        """Dispatch an observational trust report event."""
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch(
                AssistantTrustReportGeneratedEvent(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    business_id=business_id,
                    trust_score=trust_score,
                )
            )
    def _redact(self, payload: dict[str, object]) -> dict[str, object]:
        """Return a recursively redacted payload copy."""
        redacted: dict[str, object] = {}
        for key, value in payload.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted
