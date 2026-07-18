"""Stock balance repository."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import FilterParams
from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.inventory.models import StockBalance


class StockBalanceRepository(BaseRepository[StockBalance]):
    """Repository for stock balance persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, StockBalance)

    async def create(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity_on_hand: Decimal = Decimal("0.0000"),
        quantity_reserved: Decimal = Decimal("0.0000"),
        quantity_available: Decimal = Decimal("0.0000"),
    ) -> StockBalance:
        """Create a stock balance from persistence fields."""
        balance = StockBalance(
            business_id=business_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            quantity_available=quantity_available,
        )
        return await self.add(balance)

    async def update(
        self,
        balance: StockBalance,
        *,
        quantity_on_hand: Decimal | None = None,
        quantity_reserved: Decimal | None = None,
        quantity_available: Decimal | None = None,
    ) -> StockBalance:
        """Update mutable stock balance quantities."""
        if quantity_on_hand is not None:
            balance.quantity_on_hand = quantity_on_hand
        if quantity_reserved is not None:
            balance.quantity_reserved = quantity_reserved
        if quantity_available is not None:
            balance.quantity_available = quantity_available
        balance.last_updated = utc_now()
        self.session.add(balance)
        await self.session.flush()
        return balance

    async def get_by_id(self, balance_id: uuid.UUID) -> StockBalance | None:
        """Return a non-deleted stock balance by UUID."""
        statement = self._base_statement().where(StockBalance.id == balance_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_product(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> list[StockBalance]:
        """Return stock balances for a product."""
        statement = (
            self._base_statement()
            .where(
                StockBalance.business_id == business_id,
                StockBalance.product_id == product_id,
            )
            .order_by(StockBalance.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().unique().all())

    async def get_by_product_and_warehouse(
        self,
        *,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> StockBalance | None:
        """Return one stock balance for a product and warehouse."""
        statement = self._base_statement().where(
            StockBalance.business_id == business_id,
            StockBalance.product_id == product_id,
            StockBalance.warehouse_id == warehouse_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalance]:
        """Return paginated stock balances with optional filters."""
        statement = self._base_statement().where(
            StockBalance.business_id == business_id
        )
        if product_id is not None:
            statement = statement.where(StockBalance.product_id == product_id)
        if warehouse_id is not None:
            statement = statement.where(StockBalance.warehouse_id == warehouse_id)
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(StockBalance.created_at.desc())
        return await self._paginate(statement, pagination)

    async def _paginate(
        self,
        statement: Select[tuple[StockBalance]],
        pagination: PaginationParams | None,
    ) -> Page[StockBalance]:
        """Paginate a stock balance statement."""
        params = pagination or PaginationParams()
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=total,
            params=params,
        )

    async def _count_statement(self, statement: Select[tuple[StockBalance]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[StockBalance]]:
        """Return standard stock balance select with relationships loaded."""
        return (
            select(StockBalance)
            .options(
                selectinload(StockBalance.product),
                selectinload(StockBalance.warehouse),
            )
            .where(StockBalance.is_deleted.is_(False))
        )
