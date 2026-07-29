"""Business-context assistant tools."""

from pydantic import BaseModel, ConfigDict

from app.modules.assistant.models import ApprovalLevel, ToolRetryPolicy, ToolSideEffect
from app.modules.assistant.tools.base import (
    EmptyToolInput,
    ToolContext,
    ToolDefinition,
    ToolResult,
)


class BusinessContextOutput(BaseModel):
    """Business context values available to grounded assistant responses."""

    model_config = ConfigDict(extra="forbid")

    business_id: str
    business_code: str | None
    legal_name: str
    trade_name: str | None
    status: str
    membership_role: str


class GetBusinessContextTool:
    """Return the current validated business context for grounded responses."""

    name = "business.get_context"
    description = "Returns the authenticated user's validated business context."
    input_model: type[BaseModel] = EmptyToolInput
    requires_business_context = True
    side_effect = ToolSideEffect.READ
    approval_level = ApprovalLevel.NONE
    idempotency_required = False
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def definition(self) -> ToolDefinition:
        """Return provider-facing metadata for this tool."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=BusinessContextOutput.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            side_effect=self.side_effect,
        )

    async def execute(
        self,
        payload: BaseModel,
        context: ToolContext,
    ) -> ToolResult:
        """Return the business context already validated by the resolver."""
        _ = payload
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        business = context.business_context.business
        membership = context.business_context.membership
        output = BusinessContextOutput(
            business_id=str(business.id),
            business_code=business.business_code,
            legal_name=business.legal_name,
            trade_name=business.trade_name,
            status=business.status.value,
            membership_role=membership.role,
        )
        return ToolResult(tool_name=self.name, result=output.model_dump())



