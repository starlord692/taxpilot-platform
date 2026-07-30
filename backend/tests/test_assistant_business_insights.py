"""Tests for AI-004 business intelligence and insights."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.accounting.financial_statements.models import (
    BalanceSheet,
    ProfitAndLossStatement,
)
from app.modules.accounting.trial_balance.models import TrialBalance
from app.modules.assistant.events import AssistantInsightGeneratedEvent
from app.modules.assistant.insights import (
    BusinessInsightRequest,
    BusinessInsightService,
    GenerateBusinessInsightsTool,
    InsightCatalog,
    InsightCategory,
    KPIValue,
)
from app.modules.assistant.models import AssistantRunStatus, MessageRole, ToolSideEffect
from app.modules.assistant.providers import MockAssistantProvider
from app.modules.assistant.schemas import AssistantMessageRequest
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import AssistantToolRegistry, ToolContext
from app.modules.business.api.context import BusinessContext
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import (
    GSTAuditIssue,
    GSTAuditReportResponse,
    GSTReportPeriod,
    GSTReportRequest,
)
from app.modules.inventory.schemas import StockBalanceListResponse
from tests.test_assistant_core import (
    FakeAssistantConversationRepository,
    FakeAssistantUnitOfWork,
    build_business,
    build_identity_user,
    build_membership,
)

GENERATED_AT = datetime(2026, 7, 30, tzinfo=UTC)


class FakeFinancialStatementService:
    """Deterministic financial statement service fake."""

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Return a profitable P&L."""
        return ProfitAndLossStatement(
            business_id=business_id,
            generated_at=GENERATED_AT,
            revenue=[],
            expenses=[],
            total_revenue=Decimal("1000.00"),
            total_expenses=Decimal("700.00"),
            net_profit=Decimal("300.00"),
        )

    async def generate_balance_sheet(self, business_id: uuid.UUID) -> BalanceSheet:
        """Return a balanced Balance Sheet."""
        return BalanceSheet(
            business_id=business_id,
            generated_at=GENERATED_AT,
            assets=[],
            liabilities=[],
            equity=[],
            total_assets=Decimal("1000.00"),
            total_liabilities=Decimal("400.00"),
            total_equity=Decimal("600.00"),
            is_balanced=True,
        )


class FakeTrialBalanceService:
    """Deterministic Trial Balance service fake."""

    async def generate(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Return a balanced Trial Balance."""
        _ = include_zero_balances
        return TrialBalance(
            business_id=business_id,
            generated_at=GENERATED_AT,
            total_debit=Decimal("1000.00"),
            total_credit=Decimal("1000.00"),
            is_balanced=True,
            accounts=[],
        )


class FakeGSTComplianceService:
    """Deterministic GST compliance service fake."""

    async def generate_audit_report(
        self,
        request: GSTReportRequest,
    ) -> GSTAuditReportResponse:
        """Return one GST audit issue for grounding tests."""
        return GSTAuditReportResponse(
            period=GSTReportPeriod(
                business_id=request.business_id,
                financial_year="2026-2027",
                tax_period=request.tax_period,
                filing_frequency=GSTFilingFrequency.MONTHLY,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
                generated_at=GENERATED_AT,
            ),
            issues=[
                GSTAuditIssue(
                    source_type="sales_invoice",
                    source_id=uuid.uuid4(),
                    code="missing_gst_breakdown",
                    message="Document has tax amount but no GST components.",
                )
            ],
            issue_count=1,
        )


class FakeInventoryService:
    """Deterministic inventory read service fake."""

    async def list_stock_balances(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return two stock balances with one low-availability row."""
        _ = product_id
        _ = warehouse_id
        params = pagination or PaginationParams()
        items = [
            StockBalanceListResponse(
                id=uuid.uuid4(),
                business_id=business_id,
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity_on_hand=Decimal("10.0000"),
                quantity_reserved=Decimal("2.0000"),
                quantity_available=Decimal("8.0000"),
                last_updated=GENERATED_AT,
            ),
            StockBalanceListResponse(
                id=uuid.uuid4(),
                business_id=business_id,
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                quantity_on_hand=Decimal("0.0000"),
                quantity_reserved=Decimal("0.0000"),
                quantity_available=Decimal("0.0000"),
                last_updated=GENERATED_AT,
            ),
        ]
        return Page.create(items=items, total=len(items), params=params)


def build_context() -> BusinessContext:
    """Build a resolved business context for insight tests."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    return BusinessContext(business=business, membership=membership, user=user)


def build_insight_service(
    dispatcher: EventDispatcher | None = None,
) -> BusinessInsightService:
    """Build the insight service with deterministic fakes."""
    return BusinessInsightService(
        financial_statement_service=FakeFinancialStatementService(),
        trial_balance_service=FakeTrialBalanceService(),
        gst_compliance_service=FakeGSTComplianceService(),
        inventory_service=FakeInventoryService(),
        event_dispatcher=dispatcher,
    )


def test_insight_catalog_is_canonical_and_advisory_only() -> None:
    """The catalog exposes canonical read-only insight definitions."""
    definitions = InsightCatalog().list_definitions()

    assert {definition.category for definition in definitions} >= {
        InsightCategory.FINANCIAL_HEALTH,
        InsightCategory.GST_COMPLIANCE,
        InsightCategory.INVENTORY,
    }
    assert all(definition.advisory_only for definition in definitions)
    assert all(definition.source_services for definition in definitions)


def test_kpi_requires_evidence() -> None:
    """Ungrounded KPI payloads are rejected."""
    with pytest.raises(ValidationError):
        KPIValue(
            name="Unsupported metric",
            category=InsightCategory.FINANCIAL_HEALTH,
            value=Decimal("1.00"),
            unit="money",
            interpretation="No evidence should fail validation.",
            confidence=0.8,
            evidence=[],
        )


@pytest.mark.asyncio
async def test_business_insight_service_generates_grounded_report() -> None:
    """Insight generation uses deterministic service outputs and evidence."""
    events: list[AssistantInsightGeneratedEvent] = []
    dispatcher = EventDispatcher()
    dispatcher.register(AssistantInsightGeneratedEvent, events.append)
    context = build_context()

    report = await build_insight_service(dispatcher).generate(
        request=BusinessInsightRequest(
            categories=[
                InsightCategory.FINANCIAL_HEALTH,
                InsightCategory.GST_COMPLIANCE,
                InsightCategory.INVENTORY,
            ],
            tax_period="2026-07",
        ),
        business_context=context,
    )

    assert report.business_id == context.business_id
    assert report.catalog_version == "business-insight-catalog-v1"
    assert report.confidence > 0
    assert all(kpi.evidence for kpi in report.kpis)
    assert all(recommendation.evidence for recommendation in report.recommendations)
    assert {evidence.source_service for evidence in report.evidence} >= {
        "FinancialStatementService",
        "TrialBalanceService",
        "GSTComplianceService",
        "InventoryService",
    }
    assert len(events) == 1


@pytest.mark.asyncio
async def test_insight_tool_manifest_is_read_only_and_grounded() -> None:
    """The assistant insight tool declares read-only execution metadata."""
    context = build_context()
    tool = GenerateBusinessInsightsTool(build_insight_service())
    definition = tool.definition()

    result = await tool.execute(
        tool.input_model(
            categories=[InsightCategory.FINANCIAL_HEALTH],
            include_inventory=False,
        ),
        ToolContext(current_user=context.user, business_context=context),
    )

    assert definition.side_effect == ToolSideEffect.READ
    assert definition.requires_business_context is True
    assert definition.approval_level.value == "none"
    assert result.tool_name == "business.generate_insights"
    provenance = cast(dict[str, Any], result.result["provenance"])
    assert result.result["evidence"]
    assert provenance["tool_name"] == "business.generate_insights"


@pytest.mark.asyncio
async def test_insight_tool_requires_business_context() -> None:
    """Tenant context is required before insight tools execute."""
    tool = GenerateBusinessInsightsTool(build_insight_service())
    user = build_context().user

    with pytest.raises(RuntimeError):
        await tool.execute(
            tool.input_model(categories=[InsightCategory.FINANCIAL_HEALTH]),
            ToolContext(current_user=user, business_context=None),
        )


@pytest.mark.asyncio
async def test_assistant_service_uses_insight_tool_without_regressing_core_flow() -> (
    None
):
    """Insight requests flow through AI-003 orchestration and remain read-only."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    repository = FakeAssistantConversationRepository()
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    registry = AssistantToolRegistry()
    registry.register(GenerateBusinessInsightsTool(build_insight_service()))
    service = AssistantService(
        unit_of_work_factory=cast(Callable[[], AssistantUnitOfWork], lambda: uow),
        event_dispatcher=EventDispatcher(),
        provider=MockAssistantProvider(),
        tool_registry=registry,
        prompt_builder=PromptBuilder(),
    )

    response = await service.send_message(
        request=AssistantMessageRequest(
            business_id=business_id,
            message="Show me business health insights and KPIs.",
        ),
        current_user=user,
    )

    assert response.run.status == AssistantRunStatus.COMPLETED
    assert response.message.role == MessageRole.ASSISTANT
    assert "grounded KPI" in response.message.content
    assert repository.tool_calls[0].side_effect == ToolSideEffect.READ
    assert repository.execution_plans[0].approval_level.value == "none"
