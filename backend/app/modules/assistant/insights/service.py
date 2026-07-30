"""Read-only business insight generation service."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.modules.accounting.financial_statements.models import (
    BalanceSheet,
    ProfitAndLossStatement,
)
from app.modules.accounting.trial_balance.models import TrialBalance
from app.modules.assistant.events import AssistantInsightGeneratedEvent
from app.modules.assistant.insights.catalog import InsightCatalog
from app.modules.assistant.insights.evidence import InsightEvidenceBuilder
from app.modules.assistant.insights.recommendations import InsightRecommendationBuilder
from app.modules.assistant.insights.schemas import (
    BusinessInsightReport,
    BusinessInsightRequest,
    InsightCategory,
    InsightDefinition,
    InsightEvidence,
    InsightProvenance,
    InsightRecommendation,
    KPIValue,
    TrendDirection,
)
from app.modules.assistant.insights.scoring import InsightConfidenceScorer
from app.modules.business.api.context import BusinessContext
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import GSTAuditReportResponse, GSTReportRequest
from app.modules.inventory.schemas import StockBalanceListResponse

ZERO = Decimal("0.00")


class FinancialStatementServiceProtocol(Protocol):
    """Financial statement service contract used by insight generation."""

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        """Generate a Profit and Loss Statement."""
        ...

    async def generate_balance_sheet(self, business_id: uuid.UUID) -> BalanceSheet:
        """Generate a Balance Sheet."""
        ...


class TrialBalanceServiceProtocol(Protocol):
    """Trial Balance service contract used by insight generation."""

    async def generate(
        self,
        business_id: uuid.UUID,
        *,
        include_zero_balances: bool = False,
    ) -> TrialBalance:
        """Generate a Trial Balance."""
        ...


class GSTComplianceServiceProtocol(Protocol):
    """GST compliance service contract used by insight generation."""

    async def generate_audit_report(
        self,
        request: GSTReportRequest,
    ) -> GSTAuditReportResponse:
        """Generate a GST audit report."""
        ...


class InventoryServiceProtocol(Protocol):
    """Inventory read service contract used by insight generation."""

    async def list_stock_balances(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return stock balances for a business."""
        ...


class BusinessInsightService:
    """Generate grounded, read-only business insights from domain services."""

    def __init__(
        self,
        *,
        financial_statement_service: FinancialStatementServiceProtocol,
        trial_balance_service: TrialBalanceServiceProtocol,
        gst_compliance_service: GSTComplianceServiceProtocol | None = None,
        inventory_service: InventoryServiceProtocol | None = None,
        catalog: InsightCatalog | None = None,
        evidence_builder: InsightEvidenceBuilder | None = None,
        confidence_scorer: InsightConfidenceScorer | None = None,
        recommendation_builder: InsightRecommendationBuilder | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        """Initialize insight generation dependencies."""
        self._financial_statement_service = financial_statement_service
        self._trial_balance_service = trial_balance_service
        self._gst_compliance_service = gst_compliance_service
        self._inventory_service = inventory_service
        self._catalog = catalog or InsightCatalog()
        self._evidence = evidence_builder or InsightEvidenceBuilder()
        self._confidence = confidence_scorer or InsightConfidenceScorer()
        self._recommendations = recommendation_builder or InsightRecommendationBuilder()
        self._event_dispatcher = event_dispatcher

    async def generate(
        self,
        *,
        request: BusinessInsightRequest,
        business_context: BusinessContext,
        conversation_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        tool_name: str = "business.generate_insights",
        tool_manifest_version: str = "assistant-tool-manifest-v1",
    ) -> BusinessInsightReport:
        """Generate a grounded business insight report."""
        selected = self._catalog.by_category(request.categories)
        selected_categories = {definition.category for definition in selected}
        generated_at = utc_now()
        evidence: list[InsightEvidence] = []
        kpis: list[KPIValue] = []
        recommendations: list[InsightRecommendation] = []
        issue_count = 0

        if self._uses_financials(selected_categories):
            financial = await self._financial_health(
                business_context.business_id,
                generated_at=generated_at,
            )
            evidence.extend(financial.evidence)
            kpis.extend(financial.kpis)
            recommendations.extend(financial.recommendations)

        if InsightCategory.GST_COMPLIANCE in selected_categories:
            gst = await self._gst_compliance(
                request,
                business_context.business_id,
                generated_at=generated_at,
            )
            issue_count += gst.issue_count
            evidence.extend(gst.evidence)
            kpis.extend(gst.kpis)
            recommendations.extend(gst.recommendations)

        if (
            request.include_inventory
            and InsightCategory.INVENTORY in selected_categories
        ):
            inventory = await self._inventory(
                business_context.business_id,
                generated_at=generated_at,
            )
            evidence.extend(inventory.evidence)
            kpis.extend(inventory.kpis)
            recommendations.extend(inventory.recommendations)

        confidence = self._confidence.aggregate([kpi.confidence for kpi in kpis])
        if confidence == 0.0:
            confidence = self._confidence.score(
                evidence=evidence, issue_count=issue_count
            )
        source_services = sorted(
            {
                service
                for definition in selected
                for service in definition.source_services
            }
        )
        report = BusinessInsightReport(
            business_id=business_context.business_id,
            generated_at=generated_at,
            catalog_version=self._catalog.version,
            summary=self._summary(
                kpis=kpis,
                recommendations_count=len(recommendations),
            ),
            kpis=kpis,
            recommendations=recommendations,
            evidence=evidence,
            confidence=confidence,
            provenance=InsightProvenance(
                business_id=business_context.business_id,
                user_id=business_context.user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                tool_name=tool_name,
                tool_manifest_version=tool_manifest_version,
                source_services=source_services,
                generated_at=generated_at,
            ),
        )
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch(
                AssistantInsightGeneratedEvent(
                    business_id=business_context.business_id,
                    insight_type="business",
                    confidence=report.confidence,
                )
            )
        return report

    def catalog_definitions(self) -> list[InsightDefinition]:
        """Return the canonical insight catalog definitions."""
        return self._catalog.list_definitions()

    async def _financial_health(
        self,
        business_id: uuid.UUID,
        *,
        generated_at: datetime,
    ) -> "_InsightSection":
        """Generate financial KPIs from deterministic accounting services."""
        _ = generated_at
        profit_and_loss = (
            await self._financial_statement_service.generate_profit_and_loss(
                business_id
            )
        )
        balance_sheet = await self._financial_statement_service.generate_balance_sheet(
            business_id
        )
        trial_balance = await self._trial_balance_service.generate(
            business_id,
            include_zero_balances=False,
        )
        evidence = [
            self._evidence.build(
                source_type="financial_statement",
                source_service="FinancialStatementService",
                source_label="Profit and Loss Statement",
                metric="net_profit",
                value=profit_and_loss.net_profit,
                generated_at=profit_and_loss.generated_at,
            ),
            self._evidence.build(
                source_type="financial_statement",
                source_service="FinancialStatementService",
                source_label="Balance Sheet",
                metric="is_balanced",
                value=balance_sheet.is_balanced,
                generated_at=balance_sheet.generated_at,
            ),
            self._evidence.build(
                source_type="trial_balance",
                source_service="TrialBalanceService",
                source_label="Trial Balance",
                metric="is_balanced",
                value=trial_balance.is_balanced,
                generated_at=trial_balance.generated_at,
            ),
        ]
        confidence = self._confidence.score(
            evidence=evidence,
            issue_count=0
            if trial_balance.is_balanced and balance_sheet.is_balanced
            else 2,
        )
        kpis = [
            KPIValue(
                name="Net profit",
                category=InsightCategory.FINANCIAL_HEALTH,
                value=profit_and_loss.net_profit,
                unit="money",
                interpretation="Net profit from P&L Statement.",
                confidence=confidence,
                direction=self._money_direction(profit_and_loss.net_profit),
                evidence=[evidence[0]],
            ),
            KPIValue(
                name="Trial balance balanced",
                category=InsightCategory.FINANCIAL_HEALTH,
                value=trial_balance.is_balanced,
                unit="boolean",
                interpretation="Whether debit and credit totals reconcile.",
                confidence=confidence,
                evidence=[evidence[2]],
            ),
        ]
        return _InsightSection(
            evidence=evidence,
            kpis=kpis,
            recommendations=self._recommendations.financial_health(
                net_profit=profit_and_loss.net_profit,
                evidence=[evidence[0]],
                confidence=confidence,
            ),
        )

    async def _gst_compliance(
        self,
        request: BusinessInsightRequest,
        business_id: uuid.UUID,
        *,
        generated_at: datetime,
    ) -> "_GSTInsightSection":
        """Generate GST KPIs from the deterministic compliance service."""
        if self._gst_compliance_service is None or request.tax_period is None:
            evidence = [
                self._evidence.build(
                    source_type="insufficient_data",
                    source_service="BusinessInsightService",
                    source_label="GST Compliance",
                    metric="tax_period_supplied",
                    value=False,
                    generated_at=generated_at,
                )
            ]
            kpis = [
                KPIValue(
                    name="GST insight readiness",
                    category=InsightCategory.GST_COMPLIANCE,
                    value="insufficient_data",
                    unit="status",
                    interpretation="GST insights require a tax period.",
                    confidence=0.4,
                    evidence=evidence,
                )
            ]
            return _GSTInsightSection(
                evidence=evidence,
                kpis=kpis,
                recommendations=[],
                issue_count=0,
            )
        audit = await self._gst_compliance_service.generate_audit_report(
            GSTReportRequest(
                business_id=business_id,
                tax_period=request.tax_period,
                filing_frequency=GSTFilingFrequency.MONTHLY,
            )
        )
        evidence = [
            self._evidence.build(
                source_type="gst_audit_report",
                source_service="GSTComplianceService",
                source_label="GST Audit Report",
                metric="issue_count",
                value=audit.issue_count,
                period_start=audit.period.start_date,
                period_end=audit.period.end_date,
                generated_at=audit.period.generated_at,
            )
        ]
        confidence = self._confidence.score(
            evidence=evidence,
            issue_count=audit.issue_count,
        )
        kpis = [
            KPIValue(
                name="GST audit issue count",
                category=InsightCategory.GST_COMPLIANCE,
                value=audit.issue_count,
                unit="count",
                interpretation="Open GST audit issues from the compliance engine.",
                confidence=confidence,
                evidence=evidence,
            )
        ]
        return _GSTInsightSection(
            evidence=evidence,
            kpis=kpis,
            recommendations=self._recommendations.gst_audit(
                issue_count=audit.issue_count,
                evidence=evidence,
                confidence=confidence,
            ),
            issue_count=audit.issue_count,
        )

    async def _inventory(
        self,
        business_id: uuid.UUID,
        *,
        generated_at: datetime,
    ) -> "_InsightSection":
        """Generate inventory KPIs from inventory read service outputs."""
        if self._inventory_service is None:
            evidence = [
                self._evidence.build(
                    source_type="insufficient_data",
                    source_service="BusinessInsightService",
                    source_label="Inventory",
                    metric="inventory_service_available",
                    value=False,
                    generated_at=generated_at,
                )
            ]
            return _InsightSection(
                evidence=evidence,
                kpis=[
                    KPIValue(
                        name="Inventory insight readiness",
                        category=InsightCategory.INVENTORY,
                        value="insufficient_data",
                        unit="status",
                        interpretation="Inventory service is unavailable.",
                        confidence=0.4,
                        evidence=evidence,
                    )
                ],
                recommendations=[],
            )
        page = await self._inventory_service.list_stock_balances(
            business_id,
            PaginationParams(page=1, size=100),
        )
        total_available = sum((item.quantity_available for item in page.items), ZERO)
        low_available_count = sum(
            1 for item in page.items if item.quantity_available <= ZERO
        )
        evidence = [
            self._evidence.build(
                source_type="inventory_read_model",
                source_service="InventoryService",
                source_label="Stock Balances",
                metric="quantity_available",
                value=total_available,
                generated_at=generated_at,
            ),
            self._evidence.build(
                source_type="inventory_read_model",
                source_service="InventoryService",
                source_label="Stock Balances",
                metric="low_available_count",
                value=low_available_count,
                generated_at=generated_at,
            ),
        ]
        confidence = self._confidence.score(evidence=evidence)
        return _InsightSection(
            evidence=evidence,
            kpis=[
                KPIValue(
                    name="Total available stock",
                    category=InsightCategory.INVENTORY,
                    value=total_available,
                    unit="quantity",
                    interpretation="Available quantity from stock balances.",
                    confidence=confidence,
                    direction=TrendDirection.UNKNOWN,
                    evidence=[evidence[0]],
                )
            ],
            recommendations=self._recommendations.inventory_availability(
                low_available_count=low_available_count,
                evidence=[evidence[1]],
                confidence=confidence,
            ),
        )

    def _uses_financials(self, categories: set[InsightCategory]) -> bool:
        """Return whether selected categories require financial statements."""
        return bool(
            categories
            & {
                InsightCategory.FINANCIAL_HEALTH,
                InsightCategory.CASH_FLOW,
                InsightCategory.REVENUE_PROFITABILITY,
                InsightCategory.OPERATIONAL,
            }
        )

    def _money_direction(self, value: Decimal) -> TrendDirection:
        """Return directional interpretation for a monetary amount."""
        if value > ZERO:
            return TrendDirection.UP
        if value < ZERO:
            return TrendDirection.DOWN
        return TrendDirection.FLAT

    def _summary(
        self,
        *,
        kpis: list[KPIValue],
        recommendations_count: int,
    ) -> str:
        """Build a compact deterministic report summary."""
        return (
            f"Generated {len(kpis)} grounded KPI(s) and "
            f"{recommendations_count} advisory recommendation(s)."
        )


class _InsightSection:
    """Internal insight section container."""

    def __init__(
        self,
        *,
        evidence: list[InsightEvidence],
        kpis: list[KPIValue],
        recommendations: list[InsightRecommendation],
    ) -> None:
        self.evidence = evidence
        self.kpis = kpis
        self.recommendations = recommendations


class _GSTInsightSection(_InsightSection):
    """Internal GST section container with issue counts."""

    def __init__(
        self,
        *,
        evidence: list[InsightEvidence],
        kpis: list[KPIValue],
        recommendations: list[InsightRecommendation],
        issue_count: int,
    ) -> None:
        super().__init__(
            evidence=evidence,
            kpis=kpis,
            recommendations=recommendations,
        )
        self.issue_count = issue_count
