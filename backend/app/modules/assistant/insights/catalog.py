"""Canonical registry for assistant business insight definitions."""

from app.modules.assistant.insights.schemas import InsightCategory, InsightDefinition

INSIGHT_CATALOG_VERSION = "business-insight-catalog-v1"


class InsightCatalog:
    """Canonical registry of insight definitions supported by AI-004."""

    version = INSIGHT_CATALOG_VERSION

    def __init__(self) -> None:
        """Initialize canonical insight definitions."""
        self._definitions = {
            definition.key: definition for definition in self._build_definitions()
        }

    def list_definitions(self) -> list[InsightDefinition]:
        """Return all registered insight definitions."""
        return list(self._definitions.values())

    def by_category(self, categories: list[InsightCategory]) -> list[InsightDefinition]:
        """Return definitions matching requested categories."""
        if not categories:
            return self.list_definitions()
        requested = set(categories)
        return [
            definition
            for definition in self._definitions.values()
            if definition.category in requested
        ]

    def _build_definitions(self) -> list[InsightDefinition]:
        """Build the static, versioned AI-004 insight catalog."""
        return [
            InsightDefinition(
                key="financial.profitability",
                category=InsightCategory.FINANCIAL_HEALTH,
                title="Financial health",
                description="Summarizes profit, loss, and balance-sheet health.",
                source_services=[
                    "FinancialStatementService",
                    "TrialBalanceService",
                ],
            ),
            InsightDefinition(
                key="cash_flow.receivables_payables",
                category=InsightCategory.CASH_FLOW,
                title="Cash flow exposure",
                description=(
                    "Highlights cash pressure from deterministic financial outputs."
                ),
                source_services=["FinancialStatementService"],
            ),
            InsightDefinition(
                key="revenue.profitability",
                category=InsightCategory.REVENUE_PROFITABILITY,
                title="Revenue and profitability",
                description="Explains revenue, expenses, and net profit movement.",
                source_services=["FinancialStatementService"],
            ),
            InsightDefinition(
                key="gst.compliance",
                category=InsightCategory.GST_COMPLIANCE,
                title="GST and compliance",
                description=(
                    "Summarizes GST liability and audit warnings for a supplied "
                    "period."
                ),
                source_services=["GSTComplianceService"],
                requires_period=True,
            ),
            InsightDefinition(
                key="inventory.availability",
                category=InsightCategory.INVENTORY,
                title="Inventory availability",
                description="Summarizes stock availability from inventory read models.",
                source_services=["InventoryService"],
            ),
            InsightDefinition(
                key="operations.data_readiness",
                category=InsightCategory.OPERATIONAL,
                title="Operational readiness",
                description="Flags insufficient data and operational review needs.",
                source_services=[
                    "FinancialStatementService",
                    "GSTComplianceService",
                    "InventoryService",
                ],
            ),
        ]
