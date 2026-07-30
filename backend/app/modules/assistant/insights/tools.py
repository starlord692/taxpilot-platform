"""Read-only assistant tools for grounded business insights."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.insights.schemas import (
    BusinessInsightReport,
    BusinessInsightRequest,
    InsightCategory,
)
from app.modules.assistant.insights.service import BusinessInsightService
from app.modules.assistant.models import ApprovalLevel, ToolRetryPolicy, ToolSideEffect
from app.modules.assistant.tools.base import ToolContext, ToolDefinition, ToolResult


class BusinessInsightToolInput(BaseModel):
    """Input for the business insight generation tool."""

    model_config = ConfigDict(extra="forbid")

    categories: list[InsightCategory] = Field(default_factory=list)
    tax_period: str | None = None
    include_inventory: bool = True


class GenerateBusinessInsightsTool:
    """Generate grounded, read-only business intelligence insights."""

    name = "business.generate_insights"
    description = "Generates grounded business KPIs, evidence, and advisory insights."
    input_model: type[BaseModel] = BusinessInsightToolInput
    requires_business_context = True
    side_effect = ToolSideEffect.READ
    approval_level = ApprovalLevel.NONE
    idempotency_required = False
    retry_policy = ToolRetryPolicy.NEVER
    timeout_ms = 30_000

    def __init__(self, insight_service: BusinessInsightService) -> None:
        """Initialize with the deterministic insight service."""
        self._insight_service = insight_service

    def definition(self) -> ToolDefinition:
        """Return provider-facing insight capability metadata."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=BusinessInsightReport.model_json_schema(),
            capability_name=self.name,
            requires_business_context=self.requires_business_context,
            approval_level=self.approval_level,
            side_effect=self.side_effect,
            idempotency_required=self.idempotency_required,
            retry_policy=self.retry_policy,
            timeout_ms=self.timeout_ms,
            dependency_hints=[
                "FinancialStatementService",
                "TrialBalanceService",
                "GSTComplianceService",
                "InventoryService",
            ],
            authoritative_output_schema=BusinessInsightReport.model_json_schema(),
        )

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Execute the read-only insight service with validated business context."""
        if context.business_context is None:
            raise RuntimeError("Business context must be provided before execution")
        request = BusinessInsightRequest.model_validate(payload.model_dump())
        report = await self._insight_service.generate(
            request=request,
            business_context=context.business_context,
            tool_name=self.name,
        )
        return ToolResult(
            tool_name=self.name,
            result=report.model_dump(mode="json"),
        )
