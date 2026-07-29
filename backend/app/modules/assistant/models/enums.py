"""Assistant model enumerations."""

from enum import StrEnum


class ConversationStatus(StrEnum):
    """Lifecycle states for assistant conversations."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    """Supported conversation message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AssistantRunStatus(StrEnum):
    """Execution states for assistant runs."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(StrEnum):
    """Execution states for assistant tool calls."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolSideEffect(StrEnum):
    """Declared side-effect class for assistant tools."""

    READ = "read"
    WRITE = "write"


class ExecutionPlanStatus(StrEnum):
    """Lifecycle states for deterministic assistant execution plans."""

    PLANNED = "planned"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ExecutionStepStatus(StrEnum):
    """Lifecycle states for individual execution plan steps."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ExecutionMode(StrEnum):
    """Supported deterministic execution modes."""

    SINGLE = "single"
    SEQUENTIAL = "sequential"
    PARALLEL_READ_ONLY = "parallel_read_only"


class ExecutionPolicyDecision(StrEnum):
    """Policy outcomes after plan validation."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"
    REQUIRES_CLARIFICATION = "requires_clarification"


class ApprovalLevel(StrEnum):
    """Approval levels supported by assistant execution checkpoints."""

    NONE = "none"
    AUTO_ALLOWED = "auto_allowed"
    EXPLICIT_USER_APPROVAL = "explicit_user_approval"
    ORGANIZATIONAL_APPROVAL = "organizational_approval"
    BLOCKED = "blocked"


class ApprovalStatus(StrEnum):
    """Lifecycle states for assistant approval checkpoints."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ToolRetryPolicy(StrEnum):
    """Retry policies declared by assistant tool manifests."""

    NEVER = "never"
    TRANSIENT_ONLY = "transient_only"

class ContextType(StrEnum):
    """Assistant context snapshot types."""

    RUN = "run"
    SUMMARY = "summary"
    WORKFLOW = "workflow"


class ContextSource(StrEnum):
    """Permitted provenance sources for assistant context."""

    USER_MESSAGE = "user_message"
    TOOL_OUTPUT = "tool_output"
    SYSTEM_DERIVED = "system_derived"
    BUSINESS_CONTEXT = "business_context"


class EntityReferenceStatus(StrEnum):
    """Lifecycle states for conversation-scoped entity references."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REPLACED = "replaced"


class EntityResolutionConfidence(StrEnum):
    """Deterministic confidence bands for entity resolution."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class AssistantWorkflowStatus(StrEnum):
    """Lifecycle states for assistant workflow tracking."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    WAITING_FOR_USER = "waiting_for_user"
    EXECUTING_TOOLS = "executing_tools"
    READY_FOR_ACTION = "ready_for_action"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    EXPIRED = "expired"
    FAILED = "failed"


class AssistantWorkflowType(StrEnum):
    """Conversation workflow types recognized by the assistant."""

    GENERAL = "general"
    SALES_INVOICE = "sales_invoice"
    PURCHASE_INVOICE = "purchase_invoice"
    EXPENSE_REVIEW = "expense_review"
    GST_REVIEW = "gst_review"
    INVENTORY_CHECK = "inventory_check"
    DOCUMENT_REVIEW = "document_review"
    ACCOUNTING_REPORT = "accounting_report"
