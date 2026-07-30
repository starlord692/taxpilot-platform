"""Assistant orchestration service."""

import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, cast

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.context import (
    ConversationContext,
    ConversationContextBuilder,
)
from app.modules.assistant.events import (
    AssistantContextGeneratedEvent,
    AssistantConversationStartedEvent,
    AssistantEntityResolvedEvent,
    AssistantMessageReceivedEvent,
    AssistantResponseGeneratedEvent,
    AssistantRunFailedEvent,
    AssistantSummaryUpdatedEvent,
    AssistantToolExecutedEvent,
    AssistantWorkflowTransitionedEvent,
)
from app.modules.assistant.exceptions import AssistantConversationNotFoundException
from app.modules.assistant.gateway.service import AssistantProviderGateway
from app.modules.assistant.memory import ConversationSummarizer
from app.modules.assistant.memory.policies import (
    CONTEXT_SNAPSHOT_TTL_HOURS,
    CONTEXT_VERSION,
    expires_in_hours,
)
from app.modules.assistant.models import (
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantEntityReference,
    AssistantMessage,
    AssistantRun,
    AssistantToolCall,
    AssistantWorkflow,
    AssistantWorkflowStatus,
    AssistantWorkflowType,
    ContextSource,
    ContextType,
    EntityResolutionConfidence,
    MessageRole,
    ToolSideEffect,
)
from app.modules.assistant.orchestration import AssistantExecutionEngine
from app.modules.assistant.orchestration.engine import AssistantExecutionRepository
from app.modules.assistant.planning import ExecutionPlanner
from app.modules.assistant.providers import (
    AssistantProvider,
    LLMMessage,
    LLMToolDefinition,
)
from app.modules.assistant.resolution import EntityResolver
from app.modules.assistant.schemas import (
    AssistantConversationResponse,
    AssistantMessageRequest,
    AssistantResponse,
)
from app.modules.assistant.services.prompt_builder import PromptBuilder
from app.modules.assistant.tools import (
    AssistantToolExecutor,
    AssistantToolRegistry,
    ToolContext,
)
from app.modules.assistant.workflow import WorkflowTracker
from app.modules.business.api.context import (
    BusinessContext,
    BusinessContextBusinessRepository,
    BusinessContextMembershipRepository,
    resolve_business_context,
)
from app.modules.identity.models import IdentityUser


class AssistantConversationRepositoryProtocol(Protocol):
    """Repository contract required by assistant orchestration."""

    async def create_conversation(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
        language: str,
        timezone: str,
    ) -> AssistantConversation:
        """Create a conversation."""
        ...

    async def get_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantConversation | None:
        """Return a conversation scoped to the current context."""
        ...

    async def update_summary(
        self,
        conversation: AssistantConversation,
        *,
        summary: str,
    ) -> AssistantConversation:
        """Update the conversation summary."""
        ...

    async def add_message(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AssistantMessage:
        """Add a conversation message."""
        ...

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 20,
    ) -> list[AssistantMessage]:
        """List recent conversation messages."""
        ...

    async def create_run(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        prompt_version: str,
        provider_name: str,
        model_name: str,
    ) -> AssistantRun:
        """Create an assistant run."""
        ...

    async def complete_run(
        self,
        run: AssistantRun,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> AssistantRun:
        """Complete an assistant run."""
        ...

    async def fail_run(
        self,
        run: AssistantRun,
        *,
        failure_reason: str,
    ) -> AssistantRun:
        """Fail an assistant run."""
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
        """Create a tool-call audit record."""
        ...

    async def complete_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        output_payload: dict[str, object],
        latency_ms: int,
    ) -> AssistantToolCall:
        """Complete a tool-call audit record."""
        ...

    async def fail_tool_call(
        self,
        tool_call: AssistantToolCall,
        *,
        error_code: str,
        latency_ms: int,
    ) -> AssistantToolCall:
        """Fail a tool-call audit record."""
        ...

    async def list_recent_tool_calls(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 5,
    ) -> list[AssistantToolCall]:
        """List recent completed tool calls."""
        ...

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
        """Create a context snapshot."""
        ...

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
        """Create an entity reference."""
        ...

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
        """List active entity references."""
        ...

    async def get_active_workflow(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
    ) -> AssistantWorkflow | None:
        """Return the active workflow."""
        ...

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
        """Create workflow state."""
        ...

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
        """Transition workflow state."""
        ...


class AssistantUnitOfWork(Protocol):
    """Unit of Work contract required by assistant orchestration."""

    businesses: BusinessContextBusinessRepository
    business_memberships: BusinessContextMembershipRepository
    assistant_conversations: AssistantConversationRepositoryProtocol

    async def __aenter__(self) -> "AssistantUnitOfWork":
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
        """Commit current transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback current transaction."""
        ...


AssistantUnitOfWorkFactory = Callable[[], AssistantUnitOfWork]


class AssistantService:
    """Coordinate assistant conversations, tools, provider calls, and context."""

    def __init__(
        self,
        *,
        unit_of_work_factory: AssistantUnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        provider: AssistantProvider | AssistantProviderGateway,
        tool_registry: AssistantToolRegistry,
        prompt_builder: PromptBuilder,
        context_builder: ConversationContextBuilder | None = None,
        summarizer: ConversationSummarizer | None = None,
        entity_resolver: EntityResolver | None = None,
        workflow_tracker: WorkflowTracker | None = None,
        execution_planner: ExecutionPlanner | None = None,
        execution_engine: AssistantExecutionEngine | None = None,
    ) -> None:
        """Initialize with deterministic dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._tool_registry = tool_registry
        self._provider = (
            provider
            if isinstance(provider, AssistantProviderGateway)
            else AssistantProviderGateway(
                provider=provider,
                tool_registry=tool_registry,
                environment="testing",
            )
        )
        self._tool_executor = AssistantToolExecutor(tool_registry)
        self._execution_planner = execution_planner or ExecutionPlanner(tool_registry)
        self._execution_engine = execution_engine or AssistantExecutionEngine(
            tool_executor=self._tool_executor,
            event_dispatcher=event_dispatcher,
        )
        self._prompt_builder = prompt_builder
        self._context_builder = context_builder or ConversationContextBuilder()
        self._summarizer = summarizer or ConversationSummarizer()
        self._entity_resolver = entity_resolver or EntityResolver()
        self._workflow_tracker = workflow_tracker or WorkflowTracker()

    async def send_message(
        self,
        *,
        request: AssistantMessageRequest,
        current_user: IdentityUser,
    ) -> AssistantResponse:
        """Process one user message through the assistant orchestration pipeline."""
        started = time.perf_counter()
        async with self._unit_of_work_factory() as uow:
            business_context = await resolve_business_context(
                uow,
                business_id=request.business_id,
                current_user=current_user,
                entered=True,
            )
            conversation = await self._get_or_create_conversation(
                uow,
                request=request,
                current_user=current_user,
                business_context=business_context,
            )
            user_message = await uow.assistant_conversations.add_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=request.message,
                metadata={"prompt_version": self._prompt_builder.prompt_version},
            )
            await self._event_dispatcher.dispatch(
                AssistantMessageReceivedEvent(
                    conversation_id=conversation.id,
                    message_id=user_message.id,
                    business_id=business_context.business_id,
                    user_id=current_user.id,
                )
            )
            run = await uow.assistant_conversations.create_run(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                prompt_version=self._prompt_builder.prompt_version,
                provider_name=self._provider.provider_name,
                model_name=self._provider.model_name,
            )
            try:
                response = await self._complete_run(
                    uow=uow,
                    request=request,
                    conversation=conversation,
                    run=run,
                    current_user=current_user,
                    business_context=business_context,
                    started=started,
                )
            except Exception as exc:
                await uow.assistant_conversations.fail_run(
                    run,
                    failure_reason=str(exc),
                )
                await self._event_dispatcher.dispatch(
                    AssistantRunFailedEvent(
                        conversation_id=conversation.id,
                        run_id=run.id,
                        business_id=business_context.business_id,
                        error_code=type(exc).__name__,
                    )
                )
                await uow.commit()
                raise
            await uow.commit()
            return response

    async def get_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
        current_user: IdentityUser,
    ) -> AssistantConversationResponse:
        """Return a conversation within the authenticated business context."""
        async with self._unit_of_work_factory() as uow:
            await resolve_business_context(
                uow,
                business_id=business_id,
                current_user=current_user,
                entered=True,
            )
            conversation = await uow.assistant_conversations.get_conversation(
                conversation_id=conversation_id,
                business_id=business_id,
                user_id=current_user.id,
            )
            if conversation is None:
                raise AssistantConversationNotFoundException(
                    "Assistant conversation not found",
                    details={"conversation_id": str(conversation_id)},
                )
            return AssistantConversationResponse.model_validate(conversation)

    async def _get_or_create_conversation(
        self,
        uow: AssistantUnitOfWork,
        *,
        request: AssistantMessageRequest,
        current_user: IdentityUser,
        business_context: BusinessContext,
    ) -> AssistantConversation:
        """Load a conversation or create a new scoped conversation."""
        if request.conversation_id is not None:
            conversation = await uow.assistant_conversations.get_conversation(
                conversation_id=request.conversation_id,
                business_id=business_context.business_id,
                user_id=current_user.id,
            )
            if conversation is None:
                raise AssistantConversationNotFoundException(
                    "Assistant conversation not found",
                    details={"conversation_id": str(request.conversation_id)},
                )
            return conversation

        title = request.message[:80]
        conversation = await uow.assistant_conversations.create_conversation(
            business_id=business_context.business_id,
            user_id=current_user.id,
            title=title,
            language=request.language,
            timezone=request.timezone,
        )
        await self._event_dispatcher.dispatch(
            AssistantConversationStartedEvent(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                user_id=current_user.id,
            )
        )
        return conversation

    async def _complete_run(
        self,
        *,
        uow: AssistantUnitOfWork,
        request: AssistantMessageRequest,
        conversation: AssistantConversation,
        run: AssistantRun,
        current_user: IdentityUser,
        business_context: BusinessContext,
        started: float,
    ) -> AssistantResponse:
        """Execute tools, call the provider, and persist the assistant response."""
        history = await self._build_history(uow, conversation_id=conversation.id)
        context = await self._build_and_store_context(
            uow=uow,
            request=request,
            conversation=conversation,
            run=run,
            history=history,
            business_context=business_context,
        )
        prompt_messages = self._prompt_builder.build_messages(
            request=request,
            history=history,
            context=context,
        )
        tool_definitions = [
            definition.model_dump()
            for definition in self._tool_registry.definitions()
        ]
        provider_session = self._provider.create_session_context(
            prompt_version=self._prompt_builder.prompt_version,
            conversation_id=conversation.id,
            run_id=run.id,
        )
        selected_tools = await self._provider.select_tools(
            session_context=provider_session,
            messages=prompt_messages,
            tools=[
                LLMToolDefinition.model_validate(definition.model_dump())
                for definition in self._tool_registry.definitions()
            ],
        )
        tool_context = ToolContext(
            current_user=current_user,
            business_context=business_context,
        )
        execution_plan = self._execution_planner.build_plan(
            selected_tools=selected_tools,
            prompt_version=self._prompt_builder.prompt_version,
            context_version=context.context_version,
            business_id=str(business_context.business_id),
            conversation_id=str(conversation.id),
            run_id=str(run.id),
        )
        self._execution_planner.validate_structure(execution_plan)
        execution_result = await self._execution_engine.execute_plan(
            repository=cast(
                AssistantExecutionRepository,
                uow.assistant_conversations,
            ),
            plan=execution_plan,
            tool_context=tool_context,
            conversation_id=conversation.id,
            run_id=run.id,
            business_id=business_context.business_id,
            user_id=current_user.id,
        )
        tool_outputs = execution_result.tool_outputs
        audited_tool_calls = execution_result.tool_calls
        for audited_tool_call in audited_tool_calls:
            await self._event_dispatcher.dispatch(
                AssistantToolExecutedEvent(
                    run_id=run.id,
                    tool_name=audited_tool_call.tool_name,
                    business_id=business_context.business_id,
                )
            )

        provider_response = await self._provider.complete(
            session_context=provider_session,
            messages=prompt_messages,
            tool_outputs=tool_outputs,
        )
        assistant_message = await uow.assistant_conversations.add_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=provider_response.content,
            metadata={
                "prompt_version": self._prompt_builder.prompt_version,
                "context_version": context.context_version,
                "tool_count": len(tool_outputs),
                "tool_definitions": tool_definitions,
            },
        )
        completed_run = await uow.assistant_conversations.complete_run(
            run,
            input_tokens=provider_response.usage.input_tokens,
            output_tokens=provider_response.usage.output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        await self._event_dispatcher.dispatch(
            AssistantResponseGeneratedEvent(
                conversation_id=conversation.id,
                run_id=run.id,
                business_id=business_context.business_id,
            )
        )
        return AssistantResponse(
            conversation_id=conversation.id,
            message=assistant_message,
            run=completed_run,
            tool_calls=audited_tool_calls,
        )

    async def _build_and_store_context(
        self,
        *,
        uow: AssistantUnitOfWork,
        request: AssistantMessageRequest,
        conversation: AssistantConversation,
        run: AssistantRun,
        history: list[LLMMessage],
        business_context: BusinessContext,
    ) -> ConversationContext:
        """Build, persist, and audit conversation-scoped context."""
        messages = await uow.assistant_conversations.list_messages(
            conversation_id=conversation.id,
        )
        summary = self._summarizer.summarize(
            conversation=conversation,
            messages=messages,
        )
        if summary is not None and summary != conversation.summary:
            await uow.assistant_conversations.update_summary(
                conversation,
                summary=summary,
            )
            await self._event_dispatcher.dispatch(
                AssistantSummaryUpdatedEvent(
                    conversation_id=conversation.id,
                    business_id=business_context.business_id,
                    summary_version="assistant-summary-v1",
                )
            )
        now = utc_now()
        explicit_reference = self._entity_resolver.extract_entity_reference(
            message=request.message,
            source_id=run.user_message_id or run.id,
        )
        if (
            explicit_reference is not None
            and explicit_reference.entity_type is not None
        ):
            await uow.assistant_conversations.create_entity_reference(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                user_id=business_context.user_id,
                entity_type=explicit_reference.entity_type,
                entity_id=explicit_reference.entity_id,
                entity_label=(
                    explicit_reference.entity_label or explicit_reference.entity_type
                ),
                source=ContextSource.USER_MESSAGE,
                confidence=explicit_reference.confidence,
                confidence_score=explicit_reference.confidence_score,
                provenance=explicit_reference.provenance.model_dump(mode="json"),
                expires_at=explicit_reference.expires_at,
            )
            await self._event_dispatcher.dispatch(
                AssistantEntityResolvedEvent(
                    conversation_id=conversation.id,
                    business_id=business_context.business_id,
                    entity_type=explicit_reference.entity_type,
                    confidence=explicit_reference.confidence.value,
                )
            )
        active_entities = (
            await uow.assistant_conversations.list_active_entity_references(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                user_id=business_context.user_id,
                now=now,
            )
        )
        workflow = await self._transition_workflow(
            uow=uow,
            request=request,
            conversation=conversation,
            business_context=business_context,
            active_entities=active_entities,
        )
        recent_tool_calls = await uow.assistant_conversations.list_recent_tool_calls(
            conversation_id=conversation.id,
        )
        context = self._context_builder.build(
            business_context=business_context,
            conversation_id=conversation.id,
            language=conversation.language,
            timezone=conversation.timezone,
            summary=summary,
            active_workflow=workflow,
            active_entities=active_entities,
            recent_tool_calls=recent_tool_calls,
        )
        await uow.assistant_conversations.create_context_snapshot(
            conversation_id=conversation.id,
            business_id=business_context.business_id,
            user_id=business_context.user_id,
            context_version=CONTEXT_VERSION,
            context_type=ContextType.RUN,
            payload=context.model_dump(mode="json"),
            provenance=context.provenance.model_dump(mode="json"),
            expires_at=expires_in_hours(CONTEXT_SNAPSHOT_TTL_HOURS),
        )
        await self._event_dispatcher.dispatch(
            AssistantContextGeneratedEvent(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                context_version=context.context_version,
                message_count=len(history),
            )
        )
        return context

    async def _transition_workflow(
        self,
        *,
        uow: AssistantUnitOfWork,
        request: AssistantMessageRequest,
        conversation: AssistantConversation,
        business_context: BusinessContext,
        active_entities: list[AssistantEntityReference],
    ) -> AssistantWorkflow:
        """Create or update conversation-scoped workflow state."""
        active_entity_refs: list[dict[str, object]] = [
            {
                "entity_type": entity.entity_type,
                "entity_id": str(entity.entity_id) if entity.entity_id else None,
                "entity_label": entity.entity_label,
                "confidence": entity.confidence.value,
            }
            for entity in active_entities[:5]
        ]
        transition = self._workflow_tracker.build_transition(
            message=request.message,
            active_entity_refs=active_entity_refs,
        )
        workflow = await uow.assistant_conversations.get_active_workflow(
            conversation_id=conversation.id,
            business_id=business_context.business_id,
            user_id=business_context.user_id,
            now=utc_now(),
        )
        if workflow is None:
            workflow = await uow.assistant_conversations.create_workflow(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                user_id=business_context.user_id,
                workflow_type=transition.workflow_type,
                status=transition.status,
                current_step=transition.current_step,
                active_entity_refs=active_entity_refs,
                pending_decisions=transition.pending_decisions,
                provenance=transition.provenance,
                expires_at=transition.expires_at,
            )
        else:
            workflow = await uow.assistant_conversations.transition_workflow(
                workflow,
                status=transition.status,
                current_step=transition.current_step,
                active_entity_refs=active_entity_refs,
                pending_decisions=transition.pending_decisions,
                provenance=transition.provenance,
                expires_at=transition.expires_at,
            )
        await self._event_dispatcher.dispatch(
            AssistantWorkflowTransitionedEvent(
                conversation_id=conversation.id,
                business_id=business_context.business_id,
                workflow_type=workflow.workflow_type.value,
                status=workflow.status.value,
            )
        )
        return workflow

    async def _build_history(
        self,
        uow: AssistantUnitOfWork,
        *,
        conversation_id: uuid.UUID,
    ) -> list[LLMMessage]:
        """Build conversation-scoped history without long-term memory."""
        messages = await uow.assistant_conversations.list_messages(
            conversation_id=conversation_id,
        )
        return [
            LLMMessage(role=message.role.value, content=message.content)
            for message in messages
        ]
