"""Read-only assistant trust tools."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.models import ApprovalLevel, ToolRetryPolicy, ToolSideEffect
from app.modules.assistant.tools.base import ToolContext, ToolDefinition, ToolResult
from app.modules.assistant.trust.service import AssistantTrustService


class ExplainAssistantRunInput(BaseModel):
    """Input for explaining one assistant run."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID = Field(description="Conversation owning the run.")
    run_id: uuid.UUID = Field(description="Assistant run to explain.")


class ConversationAuditInput(BaseModel):
    """Input for auditing one assistant conversation."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID = Field(description="Conversation to audit.")


class ExplainAssistantRunTool:
    """Assistant tool that returns a read-only run explanation."""

    name = "assistant.explain_run"
    description = "Explain one assistant run using persisted audit records."
    input_model: type[BaseModel] = ExplainAssistantRunInput
    requires_business_context = True
    side_effect = ToolSideEffect.READ
    approval_level = ApprovalLevel.NONE
    idempotency_required = False
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, trust_service: AssistantTrustService) -> None:
        """Initialize with the assistant trust service."""
        self._trust_service = trust_service

    def definition(self) -> ToolDefinition:
        """Return the tool capability manifest."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=ExplainAssistantRunInput.model_json_schema(),
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
            capability_name="assistant_trust_explain_run",
            dependency_hints=["assistant audit records", "business context"],
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Return a read-only explanation for the requested run."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        request = ExplainAssistantRunInput.model_validate(payload.model_dump())
        report = await self._trust_service.explain_run(
            business_id=context.business_context.business_id,
            conversation_id=request.conversation_id,
            run_id=request.run_id,
            current_user=context.current_user,
        )
        return ToolResult(tool_name=self.name, result=report.model_dump(mode="json"))


class GetAssistantConversationAuditTool:
    """Assistant tool that returns a read-only conversation audit."""

    name = "assistant.audit_conversation"
    description = "Return a chronological assistant conversation audit."
    input_model: type[BaseModel] = ConversationAuditInput
    requires_business_context = True
    side_effect = ToolSideEffect.READ
    approval_level = ApprovalLevel.NONE
    idempotency_required = False
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, trust_service: AssistantTrustService) -> None:
        """Initialize with the assistant trust service."""
        self._trust_service = trust_service

    def definition(self) -> ToolDefinition:
        """Return the tool capability manifest."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=ConversationAuditInput.model_json_schema(),
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
            capability_name="assistant_trust_audit_conversation",
            dependency_hints=["assistant audit records", "business context"],
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Return a read-only audit for the requested conversation."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        request = ConversationAuditInput.model_validate(payload.model_dump())
        report = await self._trust_service.audit_conversation(
            business_id=context.business_context.business_id,
            conversation_id=request.conversation_id,
            current_user=context.current_user,
        )
        return ToolResult(tool_name=self.name, result=report.model_dump(mode="json"))
