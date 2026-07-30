"""Assistant action tools."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.actions.enums import AssistantActionType
from app.modules.assistant.actions.schemas import (
    ActionDraftCreate,
    ActionDraftResponse,
    ActionResultResponse,
    ExecutionPreview,
)
from app.modules.assistant.actions.service import AssistantActionService
from app.modules.assistant.models import ApprovalLevel, ToolRetryPolicy, ToolSideEffect
from app.modules.assistant.tools.base import ToolContext, ToolDefinition, ToolResult


class CreateActionDraftInput(BaseModel):
    """Input for creating a draft assistant action."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    action_type: AssistantActionType
    draft_payload: dict[str, object] = Field(default_factory=dict)
    source: str = "assistant"


class ActionDraftIdInput(BaseModel):
    """Input for tools that operate on one action draft."""

    model_config = ConfigDict(extra="forbid")

    draft_id: uuid.UUID


class CreateActionDraftTool:
    """Create a draft-first assistant action without mutating ERP records."""

    name = "assistant.action.create_draft"
    description = "Creates an assistant action draft and execution preview."
    input_model: type[BaseModel] = CreateActionDraftInput
    requires_business_context = True
    side_effect = ToolSideEffect.WRITE
    approval_level = ApprovalLevel.AUTO_ALLOWED
    idempotency_required = True
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, action_service: AssistantActionService) -> None:
        """Initialize with the assistant action service."""
        self._action_service = action_service

    def definition(self) -> ToolDefinition:
        """Return provider-facing metadata for this action tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=ActionDraftResponse.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            idempotency_required=self.idempotency_required,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Create and return a validated action draft."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        data = CreateActionDraftInput.model_validate(payload)
        draft = await self._action_service.create_draft(
            request=ActionDraftCreate.model_validate(data.model_dump()),
            business_context=context.business_context,
        )
        return ToolResult(
            tool_name=self.name,
            result=ActionDraftResponse.model_validate(draft).model_dump(mode="json"),
        )


class GetActionPreviewTool:
    """Return the stored execution preview for an action draft."""

    name = "assistant.action.get_preview"
    description = "Returns readiness, side effects, and approval details for a draft."
    input_model: type[BaseModel] = ActionDraftIdInput
    requires_business_context = True
    side_effect = ToolSideEffect.READ
    approval_level = ApprovalLevel.NONE
    idempotency_required = False
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, action_service: AssistantActionService) -> None:
        """Initialize with the assistant action service."""
        self._action_service = action_service

    def definition(self) -> ToolDefinition:
        """Return provider-facing metadata for this action tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=ExecutionPreview.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            idempotency_required=self.idempotency_required,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Return the execution preview for one draft."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        data = ActionDraftIdInput.model_validate(payload)
        preview = await self._action_service.execution_preview(
            draft_id=data.draft_id,
            business_context=context.business_context,
        )
        return ToolResult(tool_name=self.name, result=preview.model_dump(mode="json"))


class ExecuteApprovedActionTool:
    """Execute an approved assistant action through deterministic services."""

    name = "assistant.action.execute_approved"
    description = "Executes an approved assistant action through existing ERP services."
    input_model: type[BaseModel] = ActionDraftIdInput
    requires_business_context = True
    side_effect = ToolSideEffect.WRITE
    approval_level = ApprovalLevel.EXPLICIT_USER_APPROVAL
    idempotency_required = True
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, action_service: AssistantActionService) -> None:
        """Initialize with the assistant action service."""
        self._action_service = action_service

    def definition(self) -> ToolDefinition:
        """Return provider-facing metadata for this action tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=ActionResultResponse.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            idempotency_required=self.idempotency_required,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Execute an already approved action draft."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        data = ActionDraftIdInput.model_validate(payload)
        result = await self._action_service.execute_approved(
            draft_id=data.draft_id,
            business_context=context.business_context,
        )
        return ToolResult(
            tool_name=self.name,
            result=ActionResultResponse.model_validate(result).model_dump(mode="json"),
        )
