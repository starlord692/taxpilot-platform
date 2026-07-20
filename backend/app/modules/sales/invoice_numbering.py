"""Thread-safe, business-scoped canonical invoice numbering."""

import uuid
from datetime import date
from typing import Protocol

from app.modules.sales.domain import InvoiceNumber

MONTHS_IN_YEAR = 12


class InvoiceSequenceRepository(Protocol):
    async def reserve(
        self, business_id: uuid.UUID, financial_year: str, prefix: str
    ) -> int: ...


class InvoiceNumberService:
    """Reserve and format invoice numbers without using invoice row counts."""

    def __init__(
        self,
        pattern: str = "{prefix}/{financial_year}/{sequence:05d}",
        financial_year_start_month: int = 4,
    ) -> None:
        if not 1 <= financial_year_start_month <= MONTHS_IN_YEAR:
            raise ValueError("Financial year start month must be between 1 and 12")
        self._pattern = pattern
        self._start_month = financial_year_start_month

    async def next_number(
        self,
        repository: InvoiceSequenceRepository,
        *,
        business_id: uuid.UUID,
        invoice_date: date,
        prefix: str = "INV",
    ) -> str:
        financial_year = self.financial_year(invoice_date)
        sequence = await repository.reserve(business_id, financial_year, prefix)
        return str(
            InvoiceNumber(
                self._pattern.format(
                    prefix=prefix,
                    financial_year=financial_year,
                    sequence=sequence,
                )
            )
        )

    def financial_year(self, value: date) -> str:
        start = value.year if value.month >= self._start_month else value.year - 1
        return f"{start}-{str(start + 1)[-2:]}"
