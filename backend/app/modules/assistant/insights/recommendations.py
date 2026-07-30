"""Advisory recommendation helpers for assistant business insights."""

from decimal import Decimal

from app.modules.assistant.insights.schemas import (
    InsightCategory,
    InsightEvidence,
    InsightRecommendation,
    InsightSeverity,
)

ZERO = Decimal("0.00")


class InsightRecommendationBuilder:
    """Build advisory-only recommendations from deterministic evidence."""

    def financial_health(
        self,
        *,
        net_profit: Decimal,
        evidence: list[InsightEvidence],
        confidence: float,
    ) -> list[InsightRecommendation]:
        """Return financial health recommendations."""
        if net_profit >= ZERO:
            return [
                InsightRecommendation(
                    title="Maintain profitable operating discipline",
                    category=InsightCategory.FINANCIAL_HEALTH,
                    severity=InsightSeverity.INFO,
                    explanation=(
                        "Current deterministic statements show non-negative "
                        "net profit."
                    ),
                    suggested_action=(
                        "Continue monitoring expense growth against revenue."
                    ),
                    confidence=confidence,
                    evidence=evidence,
                    limitations=[
                        "This is advisory and depends on posted accounting data."
                    ],
                )
            ]
        return [
            InsightRecommendation(
                title="Review loss drivers",
                category=InsightCategory.FINANCIAL_HEALTH,
                severity=InsightSeverity.WARNING,
                explanation=(
                    "Current deterministic statements show expenses above revenue."
                ),
                suggested_action=(
                    "Review high-expense accounts before making operating decisions."
                ),
                confidence=confidence,
                evidence=evidence,
                limitations=[
                    "This recommendation does not create or modify ERP records."
                ],
            )
        ]

    def gst_audit(
        self,
        *,
        issue_count: int,
        evidence: list[InsightEvidence],
        confidence: float,
    ) -> list[InsightRecommendation]:
        """Return GST compliance recommendations."""
        if issue_count == 0:
            return []
        return [
            InsightRecommendation(
                title="Review GST compliance issues",
                category=InsightCategory.GST_COMPLIANCE,
                severity=InsightSeverity.WARNING,
                explanation=(
                    "GST compliance audit returned open issues for the "
                    "requested period."
                ),
                suggested_action=(
                    "Open the GST audit report and resolve source-document "
                    "mismatches."
                ),
                confidence=confidence,
                evidence=evidence,
                limitations=["GST was not recalculated by the assistant."],
            )
        ]

    def inventory_availability(
        self,
        *,
        low_available_count: int,
        evidence: list[InsightEvidence],
        confidence: float,
    ) -> list[InsightRecommendation]:
        """Return inventory availability recommendations."""
        if low_available_count == 0:
            return []
        return [
            InsightRecommendation(
                title="Review low-availability inventory",
                category=InsightCategory.INVENTORY,
                severity=InsightSeverity.WARNING,
                explanation=(
                    "One or more stock balances show zero or negative availability."
                ),
                suggested_action=(
                    "Review inventory availability before committing additional sales."
                ),
                confidence=confidence,
                evidence=evidence,
                limitations=[
                    "The assistant did not reserve, release, or adjust stock."
                ],
            )
        ]
