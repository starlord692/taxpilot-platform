"""Confidence scoring for assistant business insights."""

from app.modules.assistant.insights.schemas import InsightEvidence


class InsightConfidenceScorer:
    """Calculate deterministic confidence values for insight payloads."""

    def score(self, *, evidence: list[InsightEvidence], issue_count: int = 0) -> float:
        """Return confidence from evidence coverage and known issues."""
        if not evidence:
            return 0.0
        base = min(1.0, 0.55 + (len(evidence) * 0.08))
        penalty = min(0.4, issue_count * 0.05)
        return round(max(0.1, base - penalty), 2)

    def aggregate(self, values: list[float]) -> float:
        """Average confidence values with an insufficient-data fallback."""
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)
