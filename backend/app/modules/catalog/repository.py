"""Catalog persistence repositories."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    """Repository managing catalog item persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session."""
        super().__init__(session, CatalogItem)

    async def create(
        self,
        request: CatalogItemCreate,
        *,
        business_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> CatalogItem:
        """Create a new catalog item, attaching inventory profile if product."""
        data = request.model_dump(
            exclude={
                "stock_tracking",
                "default_warehouse_id",
                "legacy_product_id",
                "reorder_level",
            }
        )
        item = CatalogItem(
            id=item_id or uuid.uuid4(),
            business_id=business_id,
            status=CatalogItemStatus.ACTIVE,
            **data,
        )
        if request.item_type == ItemType.PRODUCT and request.stock_tracking is not False:
            item.inventory_profile = InventoryItemProfile(
                id=uuid.uuid4(),
                catalog_item_id=item.id,
                legacy_product_id=request.legacy_product_id,
                stock_tracking=True if request.stock_tracking is None else request.stock_tracking,
                reorder_level=request.reorder_level,
                default_warehouse_id=request.default_warehouse_id,
            )
        return await self.add(item)

    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None:
        """Retrieve a catalog item by ID with eager-loaded inventory profile."""
        stmt = (
            select(CatalogItem)
            .options(selectinload(CatalogItem.inventory_profile))
            .where(
                CatalogItem.id == item_id,
                CatalogItem.is_deleted.is_(False),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_ids(self, item_ids: set[uuid.UUID]) -> list[CatalogItem]:
        """Return available catalog items for a bounded identifier set."""
        if not item_ids:
            return []
        stmt = (
            select(CatalogItem)
            .options(selectinload(CatalogItem.inventory_profile))
            .where(
                CatalogItem.id.in_(item_ids),
                CatalogItem.is_deleted.is_(False),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_code(
        self, business_id: uuid.UUID, code: str
    ) -> CatalogItem | None:
        """Retrieve a catalog item by business ID and unique code."""
        stmt = (
            select(CatalogItem)
            .options(selectinload(CatalogItem.inventory_profile))
            .where(
                CatalogItem.business_id == business_id,
                CatalogItem.code == code,
                CatalogItem.is_deleted.is_(False),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update(
        self, item: CatalogItem, request: CatalogItemUpdate
    ) -> CatalogItem:
        """Update a catalog item with tax classification validation."""
        values = request.model_dump(
            exclude_unset=True,
            exclude={"default_warehouse_id", "reorder_level"},
        )
        candidate_type = values.get("item_type", item.item_type)
        TaxClassification(
            values.get("hsn_code", item.hsn_code),
            values.get("sac_code", item.sac_code),
            values.get("gst_rate", item.gst_rate),
            values.get("cess_rate", item.cess_rate),
        ).validate_for(candidate_type)
        for name, value in values.items():
            setattr(item, name, value)

        if item.inventory_profile is not None:
            if request.default_warehouse_id is not None:
                item.inventory_profile.default_warehouse_id = request.default_warehouse_id
            if request.reorder_level is not None:
                item.inventory_profile.reorder_level = request.reorder_level

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
        """List catalog items for a business with optional filtering."""
        stmt = (
            select(CatalogItem)
            .options(selectinload(CatalogItem.inventory_profile))
            .where(
                CatalogItem.business_id == business_id,
                CatalogItem.is_deleted.is_(False),
            )
        )
        if item_type is not None:
            stmt = stmt.where(CatalogItem.item_type == item_type)
        if status is not None:
            stmt = stmt.where(CatalogItem.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self.session.execute(count_stmt)).scalar_one())

        rows_stmt = (
            stmt.order_by(CatalogItem.name)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        rows = (await self.session.execute(rows_stmt)).scalars().all()
        return Page.create(items=list(rows), total=total, params=pagination)


class InventoryItemProfileRepository(BaseRepository[InventoryItemProfile]):
    """Repository managing inventory item capability profiles."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session."""
        super().__init__(session, InventoryItemProfile)

    async def get_by_catalog_item_id(
        self, catalog_item_id: uuid.UUID
    ) -> InventoryItemProfile | None:
        """Retrieve an inventory profile by its catalog item ID."""
        stmt = select(InventoryItemProfile).where(
            InventoryItemProfile.catalog_item_id == catalog_item_id,
            InventoryItemProfile.is_deleted.is_(False),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_for_legacy_product(
        self,
        *,
        item_id: uuid.UUID,
        product_id: uuid.UUID,
        reorder_level: object = None,
        default_warehouse_id: uuid.UUID | None = None,
    ) -> InventoryItemProfile:
        """Create an inventory profile linking a catalog item to an inventory product."""
        return await self.add(
            InventoryItemProfile(
                id=uuid.uuid4(),
                catalog_item_id=item_id,
                legacy_product_id=product_id,
                stock_tracking=True,
                reorder_level=reorder_level,
                default_warehouse_id=default_warehouse_id,
            )
        )
