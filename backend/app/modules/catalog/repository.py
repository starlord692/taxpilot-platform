"""Catalog persistence repositories."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.catalog.domain import TaxClassification
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemStatus,
    InventoryItemProfile,
    ItemType,
)
from app.modules.catalog.schemas import CatalogItemCreate, CatalogItemUpdate


class CatalogItemRepository(BaseRepository[CatalogItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CatalogItem)

    async def create(
        self,
        request: CatalogItemCreate,
        *,
        business_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> CatalogItem:
        item = CatalogItem(
            id=item_id or uuid.uuid4(),
            business_id=business_id,
            status=CatalogItemStatus.ACTIVE,
            **request.model_dump(),
        )
        return await self.add(item)

    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None:
        return (
            await self.session.execute(
                select(CatalogItem).where(
                    CatalogItem.id == item_id, CatalogItem.is_deleted.is_(False)
                )
            )
        ).scalar_one_or_none()

    async def get_by_ids(self, item_ids: set[uuid.UUID]) -> list[CatalogItem]:
        """Return available catalog items for a bounded identifier set."""
        if not item_ids:
            return []
        result = await self.session.execute(
            select(CatalogItem).where(
                CatalogItem.id.in_(item_ids), CatalogItem.is_deleted.is_(False)
            )
        )
        return list(result.scalars().all())

    async def get_by_code(
        self, business_id: uuid.UUID, code: str
    ) -> CatalogItem | None:
        return (
            await self.session.execute(
                select(CatalogItem).where(
                    CatalogItem.business_id == business_id,
                    CatalogItem.code == code,
                    CatalogItem.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def update(
        self, item: CatalogItem, request: CatalogItemUpdate
    ) -> CatalogItem:
        values = request.model_dump(exclude_unset=True)
        candidate_type = values.get("item_type", item.item_type)
        TaxClassification(
            values.get("hsn_code", item.hsn_code),
            values.get("sac_code", item.sac_code),
            values.get("gst_rate", item.gst_rate),
            values.get("cess_rate", item.cess_rate),
        ).validate_for(candidate_type)
        for name, value in values.items():
            setattr(item, name, value)
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_items(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        item_type: ItemType | None = None,
        status: CatalogItemStatus | None = None,
    ) -> Page[CatalogItem]:
        stmt = select(CatalogItem).where(
            CatalogItem.business_id == business_id, CatalogItem.is_deleted.is_(False)
        )
        if item_type:
            stmt = stmt.where(CatalogItem.item_type == item_type)
        if status:
            stmt = stmt.where(CatalogItem.status == status)
        total = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).scalar_one()
        )
        rows = (
            (
                await self.session.execute(
                    stmt.order_by(CatalogItem.name)
                    .offset(pagination.offset)
                    .limit(pagination.limit)
                )
            )
            .scalars()
            .all()
        )
        return Page.create(items=list(rows), total=total, params=pagination)


class InventoryItemProfileRepository(BaseRepository[InventoryItemProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InventoryItemProfile)

    async def create_for_legacy_product(
        self, *, item_id: uuid.UUID, product_id: uuid.UUID, reorder_level: object
    ) -> InventoryItemProfile:
        return await self.add(
            InventoryItemProfile(
                id=item_id,
                catalog_item_id=item_id,
                legacy_product_id=product_id,
                stock_tracking=True,
                reorder_level=reorder_level,
            )
        )
