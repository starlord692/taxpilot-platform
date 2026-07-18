"""GST tax rate repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.gst.models import GSTTaxRate
from app.modules.gst.schemas import GSTTaxRateCreate, GSTTaxRateUpdate


class GSTTaxRateRepository(BaseRepository[GSTTaxRate]):
    """Repository for GST tax rate persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, GSTTaxRate)

    async def create(self, request: GSTTaxRateCreate) -> GSTTaxRate:
        """Create a GST tax rate."""
        return await self.add(GSTTaxRate(**request.model_dump()))

    async def update(
        self,
        tax_rate: GSTTaxRate,
        request: GSTTaxRateUpdate,
    ) -> GSTTaxRate:
        """Update GST tax rate fields."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(tax_rate, field_name, value)
        self.session.add(tax_rate)
        await self.session.flush()
        return tax_rate

    async def deactivate(self, tax_rate: GSTTaxRate) -> GSTTaxRate:
        """Deactivate a GST tax rate."""
        tax_rate.is_active = False
        self.session.add(tax_rate)
        await self.session.flush()
        return tax_rate

    async def get_by_id(self, tax_rate_id: uuid.UUID) -> GSTTaxRate | None:
        """Return tax rate by UUID."""
        result = await self.session.execute(
            self._base_statement().where(GSTTaxRate.id == tax_rate_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> GSTTaxRate | None:
        """Return tax rate by name."""
        result = await self.session.execute(
            self._base_statement().where(GSTTaxRate.name == name.strip())
        )
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        pagination: PaginationParams | None = None,
        active_only: bool = False,
    ) -> Page[GSTTaxRate]:
        """List GST tax rates."""
        statement = self._base_statement()
        if active_only:
            statement = statement.where(GSTTaxRate.is_active.is_(True))
        statement = statement.order_by(GSTTaxRate.effective_from.desc())
        return await self._paginate(statement, pagination)

    async def _paginate(
        self,
        statement: Select[tuple[GSTTaxRate]],
        pagination: PaginationParams | None,
    ) -> Page[GSTTaxRate]:
        """Paginate tax rate rows."""
        params = pagination or PaginationParams()
        total_result = await self.session.execute(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=int(total_result.scalar_one()),
            params=params,
        )

    def _base_statement(self) -> Select[tuple[GSTTaxRate]]:
        """Return default select."""
        return select(GSTTaxRate).where(GSTTaxRate.is_deleted.is_(False))
