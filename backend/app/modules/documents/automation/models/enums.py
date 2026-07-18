"""Document automation enums."""

from enum import StrEnum


class AutomationState(StrEnum):
    """Automation run lifecycle state."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class AutomationType(StrEnum):
    """Supported ERP automation targets."""

    SALES = "sales"
    PURCHASE = "purchase"
    EXPENSE = "expense"
