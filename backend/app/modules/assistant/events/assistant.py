"""Assistant domain events."""

import uuid
from dataclasses import dataclass

from app.common.events import Event


@dataclass(frozen=True)
class AssistantConversationStartedEvent(Event):
    """Published after a conversation is created."""

    event_name = "assistant.conversation_started"
    conversation_id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class AssistantMessageReceivedEvent(Event):
    """Published after a user message is persisted."""

    event_name = "assistant.message_received"
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class AssistantContextGeneratedEvent(Event):
    """Published after conversation-scoped context is generated."""

    event_name = "assistant.context_generated"
    conversation_id: uuid.UUID
    business_id: uuid.UUID
    context_version: str
    message_count: int


@dataclass(frozen=True)
class AssistantSummaryUpdatedEvent(Event):
    """Published after the conversation-scoped summary is refreshed."""

    event_name = "assistant.summary_updated"
    conversation_id: uuid.UUID
    business_id: uuid.UUID
    summary_version: str


@dataclass(frozen=True)
class AssistantEntityResolvedEvent(Event):
    """Published after an entity reference is resolved for a conversation."""

    event_name = "assistant.entity_resolved"
    conversation_id: uuid.UUID
    business_id: uuid.UUID
    entity_type: str
    confidence: str


@dataclass(frozen=True)
class AssistantWorkflowTransitionedEvent(Event):
    """Published after assistant workflow state changes."""

    event_name = "assistant.workflow_transitioned"
    conversation_id: uuid.UUID
    business_id: uuid.UUID
    workflow_type: str
    status: str


@dataclass(frozen=True)
class AssistantToolExecutedEvent(Event):
    """Published after a permitted assistant tool completes."""

    event_name = "assistant.tool_executed"
    run_id: uuid.UUID
    tool_name: str
    business_id: uuid.UUID


@dataclass(frozen=True)
class AssistantResponseGeneratedEvent(Event):
    """Published after an assistant response is persisted."""

    event_name = "assistant.response_generated"
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID


@dataclass(frozen=True)
class AssistantRunFailedEvent(Event):
    """Published after an assistant run fails."""

    event_name = "assistant.run_failed"
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID
    error_code: str


@dataclass(frozen=True)
class AssistantExecutionPlanCreatedEvent(Event):
    """Published after an assistant execution plan is persisted."""

    event_name = "assistant.execution_plan_created"
    plan_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID
    plan_version: str


@dataclass(frozen=True)
class AssistantExecutionPolicyEvaluatedEvent(Event):
    """Published after execution policy evaluates a plan."""

    event_name = "assistant.execution_policy_evaluated"
    plan_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID
    decision: str


@dataclass(frozen=True)
class AssistantApprovalCheckpointCreatedEvent(Event):
    """Published after an approval checkpoint is created."""

    event_name = "assistant.approval_checkpoint_created"
    plan_id: uuid.UUID
    business_id: uuid.UUID
    approval_level: str


@dataclass(frozen=True)
class AssistantExecutionCompletedEvent(Event):
    """Published after an execution plan completes."""

    event_name = "assistant.execution_completed"
    plan_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID


@dataclass(frozen=True)
class AssistantExecutionFailedEvent(Event):
    """Published after an execution plan fails."""

    event_name = "assistant.execution_failed"
    plan_id: uuid.UUID
    run_id: uuid.UUID
    business_id: uuid.UUID
    error_code: str
