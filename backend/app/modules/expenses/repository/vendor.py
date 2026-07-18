"""Vendor repository."""

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.filters import FilterParams
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.expenses.models import Vendor
from app.modules.expenses.schemas import VendorCreate, VendorUpdate


class VendorRepository(BaseRepository[Vendor]):
    """Repository for vendor persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Vendor)

    async def create(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor:
        """Create a vendor from request data and persistence identifiers."""
        vendor = Vendor(
            **request.model_dump(),
            business_id=business_id,
            vendor_code=vendor_code,
        )
        return await self.add(vendor)

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        """Return a non-deleted vendor by UUID."""
        statement = select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_vendor_code(
        self,
        *,
        business_id: uuid.UUID,
        vendor_code: str,
    ) -> Vendor | None:
        """Return a vendor by business-scoped vendor code."""
        statement = select(Vendor).where(
            Vendor.business_id == business_id,
            Vendor.vendor_code == vendor_code,
            Vendor.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        filters: FilterParams | None = None,
        sort: str | None = None,
    ) -> Page[Vendor]:
        """Return paginated vendors for a business."""
        statement = self._base_statement().where(Vendor.business_id == business_id)
        statement = self._apply_filters(statement, filters)
        statement = self._apply_vendor_sort(statement, sort)
        return await self._paginate(statement, pagination)

    async def update(self, vendor: Vendor, request: VendorUpdate) -> Vendor:
        """Update mutable vendor fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(vendor, field_name, value)
        self.session.add(vendor)
        await self.session.flush()
        return vendor

    async def delete(self, vendor: Vendor) -> None:
        """Soft-delete a vendor."""
        await super().delete(vendor)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Vendor]:
        """Search business vendors by name, code, email, GSTIN, or PAN."""
        search_pattern = f"%{query.strip()}%"
        statement = self._base_statement().where(
            Vendor.business_id == business_id,
            or_(
                Vendor.name.ilike(search_pattern),
                Vendor.vendor_code.ilike(search_pattern),
                Vendor.email.ilike(search_pattern),
                Vendor.gstin.ilike(search_pattern),
                Vendor.pan.ilike(search_pattern),
            ),
        )
        statement = self._apply_vendor_sort(statement, "name")
        return await self._paginate(statement, pagination)

    async def _paginate(
        self,
        statement: Select[tuple[Vendor]],
        pagination: PaginationParams | None,
    ) -> Page[Vendor]:
        """Paginate a vendor statement."""
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

    async def _count_statement(self, statement: Select[tuple[Vendor]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_statement(self) -> Select[tuple[Vendor]]:
        """Return standard vendor select."""
        return select(Vendor).where(Vendor.is_deleted.is_(False))

    def _apply_vendor_sort(
        self,
        statement: Select[tuple[Vendor]],
        sort: str | None,
    ) -> Select[tuple[Vendor]]:
        """Apply supported vendor sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Vendor.created_at,
            "name": Vendor.name,
            "vendor_code": Vendor.vendor_code,
            "email": Vendor.email,
            "is_active": Vendor.is_active,
        }
        column = sort_columns.get(field_name, Vendor.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
