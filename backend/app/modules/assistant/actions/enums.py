"""Assistant action enumerations."""

from enum import StrEnum


class AssistantActionType(StrEnum):
    """Supported assistant-guided ERP action types."""

    SALES_INVOICE_CREATE_DRAFT = "sales.invoice.create_draft"
    PURCHASE_INVOICE_CREATE_DRAFT = "purchase.invoice.create_draft"
    EXPENSE_CREATE_DRAFT = "expense.create_draft"
    VENDOR_CREATE_DRAFT = "vendor.create_draft"
    PAYMENT_RECORD = "payment.record"


class AssistantActionStatus(StrEnum):
    """Lifecycle states for assistant action drafts."""

    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ActionReadinessStatus(StrEnum):
    """Readiness states before an action can be approved or executed."""

    READY = "ready"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"
    INVALID = "invalid"


class ReadinessSeverity(StrEnum):
    """Readiness finding severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AssistantActionResultStatus(StrEnum):
    """Execution result states for assistant actions."""

    COMPLETED = "completed"
    FAILED = "failed"
    REPLAYED = "replayed"
