"""Supplier repository."""

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.purchases.models import Supplier
from app.modules.purchases.schemas import SupplierCreate, SupplierUpdate


class SupplierRepository(BaseRepository[Supplier]):
    """Repository for supplier persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Supplier)

    async def create(
        self,
        request: SupplierCreate,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier:
        """Create a supplier from request data and persistence identifiers."""
        supplier = Supplier(
            **request.model_dump(),
            business_id=business_id,
            supplier_code=supplier_code,
        )
        return await self.add(supplier)

    async def update(self, supplier: Supplier, request: SupplierUpdate) -> Supplier:
        """Update mutable supplier fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(supplier, field_name, value)
        self.session.add(supplier)
        await self.session.flush()
        return supplier

    async def delete(self, supplier: Supplier) -> None:
        """Soft-delete a supplier."""
        await super().delete(supplier)

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        """Return a non-deleted supplier by UUID."""
        statement = self._base_statement().where(Supplier.id == supplier_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_supplier_code(
        self,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier | None:
        """Return a supplier by business-scoped supplier code."""
        statement = self._base_statement().where(
            Supplier.business_id == business_id,
            Supplier.supplier_code == supplier_code,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_gstin(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
    ) -> Supplier | None:
        """Return a supplier by business-scoped GSTIN."""
        statement = self._base_statement().where(
            Supplier.business_id == business_id,
            Supplier.gstin == gstin.upper(),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        filters: FilterParams | None = None,
        sort: str | None = None,
    ) -> Page[Supplier]:
        """Return paginated suppliers for a business."""
        statement = self._base_statement().where(Supplier.business_id == business_id)
        statement = self._apply_filters(statement, filters)
        statement = self._apply_supplier_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Supplier]:
        """Search business suppliers by name, code, or GSTIN."""
        search_pattern = f"%{query.strip()}%"
        statement = self._base_statement().where(
            Supplier.business_id == business_id,
            or_(
                Supplier.name.ilike(search_pattern),
                Supplier.supplier_code.ilike(search_pattern),
                Supplier.gstin.ilike(search_pattern),
            ),
        )
        statement = self._apply_supplier_sort(statement, "name")
        return await self._paginate(statement, pagination)

    async def exists(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        supplier_code: str | None = None,
        gstin: str | None = None,
    ) -> bool:
        """Return whether a supplier exists for supplied business keys."""
        statement = self._base_statement().where(Supplier.business_id == business_id)
        if supplier_code is not None:
            statement = statement.where(Supplier.supplier_code == supplier_code)
        if gstin is not None:
            statement = statement.where(Supplier.gstin == gstin.upper())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def _paginate(
        self,
        statement: Select[tuple[Supplier]],
        pagination: PaginationParams | None,
    ) -> Page[Supplier]:
        """Paginate a supplier statement."""
        params = pagination or PaginationParams()
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=total,
            params=params,
        )

    async def _count_statement(self, statement: Select[tuple[Supplier]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[Supplier]]:
        """Return standard supplier select."""
        return select(Supplier).where(Supplier.is_deleted.is_(False))

    def _apply_supplier_sort(
        self,
        statement: Select[tuple[Supplier]],
        sort: str | None,
    ) -> Select[tuple[Supplier]]:
        """Apply supported supplier sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Supplier.created_at,
            "name": Supplier.name,
            "supplier_code": Supplier.supplier_code,
            "email": Supplier.email,
            "is_active": Supplier.is_active,
        }
        column: Any = sort_columns.get(field_name, Supplier.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
