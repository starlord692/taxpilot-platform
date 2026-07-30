"""Evidence helpers for assistant business insights."""

from datetime import date, datetime
from decimal import Decimal

from app.modules.assistant.insights.schemas import InsightEvidence


class InsightEvidenceBuilder:
    """Create normalized evidence entries for deterministic source outputs."""

    def build(
        self,
        *,
        source_type: str,
        source_service: str,
        source_label: str,
        metric: str,
        value: Decimal | str | bool | int,
        generated_at: datetime,
        source_id: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> InsightEvidence:
        """Build one evidence object."""
        return InsightEvidence(
            source_type=source_type,
            source_service=source_service,
            source_id=source_id,
            source_label=source_label,
            metric=metric,
            value=value,
            period_start=period_start,
            period_end=period_end,
            generated_at=generated_at,
        )
