"""Catalog domain, schema, service, and compatibility tests."""

import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Self, cast

import pytest
from pydantic import ValidationError

from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.catalog.domain import TaxClassification
from app.modules.catalog.events import CatalogItemCreatedEvent
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemStatus,
    InventoryItemProfile,
    ItemType,
)
from app.modules.catalog.schemas import CatalogItemCreate, CatalogItemUpdate
from app.modules.catalog.service import CatalogService, CatalogUnitOfWork


def request(item_type: ItemType = ItemType.PRODUCT) -> CatalogItemCreate:
    return CatalogItemCreate(
        code="ITEM-1",
        name="Consulting" if item_type is ItemType.SERVICE else "Laptop",
        item_type=item_type,
        default_unit="hour" if item_type is ItemType.SERVICE else "pcs",
        sac_code="998311" if item_type is ItemType.SERVICE else None,
        hsn_code="84713010" if item_type is ItemType.PRODUCT else None,
        gst_rate=Decimal("18.00"),
    )


def test_product_and_service_tax_classification() -> None:
    assert request(ItemType.PRODUCT).hsn_code == "84713010"
    assert request(ItemType.SERVICE).sac_code == "998311"
    with pytest.raises(ValidationError):
        CatalogItemCreate(
            name="Invalid product",
            item_type=ItemType.PRODUCT,
            default_unit="pcs",
            sac_code="998311",
        )
    with pytest.raises(ValueError, match="between 0 and 100"):
        TaxClassification(gst_rate=Decimal("101")).validate_for(ItemType.PRODUCT)


def test_catalog_serialization_has_no_inventory_requirement() -> None:
    item = request(ItemType.SERVICE)
    payload = item.model_dump(mode="json")
    assert payload["item_type"] == "service"
    assert "reorder_level" not in payload
    assert "stock_tracking" not in payload


class CapturingDispatcher(EventDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        self.events.append(event)


class FakeCatalogRepository:
    def __init__(self) -> None:
        self.items: list[CatalogItem] = []

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
        self.items.append(item)
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None:
        return next((item for item in self.items if item.id == item_id), None)

    async def get_by_code(
        self, business_id: uuid.UUID, code: str
    ) -> CatalogItem | None:
        return next(
            (
                item
                for item in self.items
                if item.business_id == business_id and item.code == code
            ),
            None,
        )

    async def update(
        self, item: CatalogItem, request: CatalogItemUpdate
    ) -> CatalogItem:
        for name, field_value in request.model_dump(exclude_unset=True).items():
            setattr(item, name, field_value)
        return item

    async def list_items(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        item_type: ItemType | None = None,
        status: CatalogItemStatus | None = None,
    ) -> Page[CatalogItem]:
        values = [item for item in self.items if item.business_id == business_id]
        if item_type:
            values = [item for item in values if item.item_type is item_type]
        if status:
            values = [item for item in values if item.status is status]
        return Page.create(items=values, total=len(values), params=pagination)


class FakeUnitOfWork:
    def __init__(self, repository: FakeCatalogRepository) -> None:
        self.catalog_items = repository
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_catalog_service_creates_services_and_publishes_event() -> None:
    repository = FakeCatalogRepository()
    uow = FakeUnitOfWork(repository)
    dispatcher = CapturingDispatcher()
    service = CatalogService(
        # The fake UoW provides the CatalogUnitOfWork protocol used by the service.
        cast(Callable[[], CatalogUnitOfWork], lambda: uow),
        dispatcher,
    )
    business_id = uuid.uuid4()

    created = await service.create(request(ItemType.SERVICE), business_id)

    assert created.item_type is ItemType.SERVICE
    assert uow.committed
    assert isinstance(dispatcher.events[0], CatalogItemCreatedEvent)
    assert dispatcher.events[0].catalog_item_id == created.id


def test_rc1_baseline_preserves_legacy_product_identifier_mapping() -> None:
    migration = Path("alembic/versions/20260726_0001_rc1_baseline.py").read_text()
    assert "legacy_product_id UUID" in migration
    assert "UNIQUE (legacy_product_id)" in migration
    assert (
        "FOREIGN KEY(legacy_product_id) "
        "REFERENCES inventory_products (id) ON DELETE SET NULL"
    ) in migration
    assert CatalogItem.__tablename__ == "catalog_items"
    assert InventoryItemProfile.__tablename__ == "inventory_item_profiles"


def test_catalog_api_contract_is_registered_without_breaking_inventory() -> None:
    paths = create_app(initialize_resources=False).openapi()["paths"]
    assert "/api/v1/catalog/items" in paths
    assert "/api/v1/catalog/items/{item_id}/archive" in paths
    assert "/api/v1/catalog/items/{item_id}/restore" in paths
    assert "/api/v1/inventory/products" in paths
