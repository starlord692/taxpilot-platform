"""Document automation events."""

import uuid
from dataclasses import dataclass

from app.common.events import Event
from app.modules.documents.automation.models import AutomationType


@dataclass(frozen=True)
class AutomationStartedEvent(Event):
    """Event published when ERP automation starts."""

    run_id: uuid.UUID
    document_id: uuid.UUID
    business_id: uuid.UUID
    automation_type: AutomationType
    event_name: str = "document.automation_started"


@dataclass(frozen=True)
class AutomationCompletedEvent(Event):
    """Event published when ERP automation completes."""

    run_id: uuid.UUID
    document_id: uuid.UUID
    business_id: uuid.UUID
    erp_record_type: str
    erp_record_id: uuid.UUID
    event_name: str = "document.automation_completed"


@dataclass(frozen=True)
class AutomationFailedEvent(Event):
    """Event published when ERP automation fails."""

    run_id: uuid.UUID
    document_id: uuid.UUID
    business_id: uuid.UUID
    reason: str
    event_name: str = "document.automation_failed"


@dataclass(frozen=True)
class AutomationRolledBackEvent(Event):
    """Event published when ERP automation is rolled back."""

    run_id: uuid.UUID
    document_id: uuid.UUID
    business_id: uuid.UUID
    reason: str
    event_name: str = "document.automation_rolled_back"
