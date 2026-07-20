"""Persistence for canonical invoice sequences."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sales.models import InvoiceNumberSequence


class InvoiceNumberSequenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reserve(
        self, business_id: uuid.UUID, financial_year: str, prefix: str
    ) -> int:
        statement = (
            insert(InvoiceNumberSequence)
            .values(
                id=uuid.uuid4(),
                business_id=business_id,
                financial_year=financial_year,
                prefix=prefix,
                next_value=1,
            )
            .on_conflict_do_nothing(
                constraint="uq_sales_invoice_sequence_business_year"
            )
        )
        await self.session.execute(statement)
        result = await self.session.execute(
            select(InvoiceNumberSequence)
            .where(
                InvoiceNumberSequence.business_id == business_id,
                InvoiceNumberSequence.financial_year == financial_year,
            )
            .with_for_update()
        )
        sequence = result.scalar_one()
        value = sequence.next_value
        sequence.next_value += 1
        self.session.add(sequence)
        await self.session.flush()
        return value
