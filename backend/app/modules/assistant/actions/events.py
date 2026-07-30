"""Assistant action domain events."""

import uuid
from dataclasses import dataclass

from app.common.events import Event


@dataclass(frozen=True)
class AssistantActionDraftCreatedEvent(Event):
    """Published after an assistant action draft is created."""

    event_name = "assistant.action_draft_created"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    action_type: str


@dataclass(frozen=True)
class AssistantActionReadinessValidatedEvent(Event):
    """Published after action readiness validation completes."""

    event_name = "assistant.action_readiness_validated"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    readiness_status: str


@dataclass(frozen=True)
class AssistantActionApprovalRequestedEvent(Event):
    """Published after an assistant action requires approval."""

    event_name = "assistant.action_approval_requested"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    approval_level: str


@dataclass(frozen=True)
class AssistantActionExecutionStartedEvent(Event):
    """Published before an approved action executes."""

    event_name = "assistant.action_execution_started"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    action_type: str


@dataclass(frozen=True)
class AssistantActionCompletedEvent(Event):
    """Published after a controlled assistant action completes."""

    event_name = "assistant.action_completed"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    erp_record_type: str | None
    erp_record_id: uuid.UUID | None


@dataclass(frozen=True)
class AssistantActionFailedEvent(Event):
    """Published after a controlled assistant action fails."""

    event_name = "assistant.action_failed"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    error_code: str


@dataclass(frozen=True)
class AssistantActionReplayedEvent(Event):
    """Published when a completed action is returned idempotently."""

    event_name = "assistant.action_replayed"
    draft_id: uuid.UUID
    business_id: uuid.UUID
    idempotency_key: str
