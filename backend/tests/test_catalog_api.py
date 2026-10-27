"""Tests for Canonical Catalog API and Service."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.catalog.api.dependencies import (
    get_catalog_service,
    get_catalog_unit_of_work,
)
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemStatus,
    InventoryItemProfile,
    ItemType,
)
from app.modules.catalog.schemas import (
    CatalogItemCreate,
    CatalogItemUpdate,
)
from app.modules.catalog.service import CatalogService
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

pytestmark = pytest.mark.asyncio


class FakeCatalogItemRepository:
    """In-memory catalog item repository for tests."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, CatalogItem] = {}

    async def create(
        self,
        request: CatalogItemCreate,
        *,
        business_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> CatalogItem:
        resolved_item_id = item_id or uuid.uuid4()
        item = CatalogItem(
            id=resolved_item_id,
            business_id=business_id,
            name=request.name,
            code=request.code,
            item_type=request.item_type,
            status=CatalogItemStatus.ACTIVE,
            description=request.description,
            category=request.category,
            purchase_price=request.purchase_price,
            selling_price=request.selling_price,
            default_unit=request.default_unit,
            barcode=request.barcode,
            hsn_code=request.hsn_code,
            sac_code=request.sac_code,
            gst_rate=request.gst_rate,
            cess_rate=request.cess_rate,
        )
        if request.stock_tracking is not None or request.legacy_product_id is not None:
            profile = InventoryItemProfile(
                id=uuid.uuid4(),
                catalog_item_id=resolved_item_id,
                stock_tracking=request.stock_tracking if request.stock_tracking is not None else True,
                legacy_product_id=request.legacy_product_id,
                default_warehouse_id=request.default_warehouse_id,
                reorder_level=request.reorder_level,
            )
            item.inventory_profile = profile
        self.items[resolved_item_id] = item
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None:
        return self.items.get(item_id)

    async def get_by_ids(
        self,
        business_id: uuid.UUID,
        item_ids: list[uuid.UUID],
    ) -> list[CatalogItem]:
        return [
            item
            for item in self.items.values()
            if item.business_id == business_id and item.id in item_ids
        ]

    async def get_by_code(
        self,
        business_id: uuid.UUID,
        code: str,
    ) -> CatalogItem | None:
        for item in self.items.values():
            if item.business_id == business_id and item.code == code:
                return item
        return None

    async def update(
        self,
        item: CatalogItem,
        request: CatalogItemUpdate,
    ) -> CatalogItem:
        update_data = request.model_dump(
            exclude_unset=True,
            exclude={"default_warehouse_id", "reorder_level"},
        )
        for key, value in update_data.items():
            setattr(item, key, value)
        return item

    async def list_items(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        item_type: ItemType | None = None,
        status: CatalogItemStatus | None = None,
    ) -> Page[CatalogItem]:
        filtered = [
            i for i in self.items.values()
            if i.business_id == business_id
        ]
        if status is not None:
            filtered = [i for i in filtered if i.status == status]
        if item_type is not None:
            filtered = [i for i in filtered if i.item_type == item_type]
        return Page.create(
            items=filtered[pagination.offset : pagination.offset + pagination.limit],
            total=len(filtered),
            params=pagination,
        )


class FakeInventoryItemProfileRepository:
    """In-memory inventory item profile repository."""

    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, InventoryItemProfile] = {}

    async def create(self, **kwargs) -> InventoryItemProfile:
        profile = InventoryItemProfile(id=uuid.uuid4(), **kwargs)
        self.profiles[profile.catalog_item_id] = profile
        return profile

    async def get_by_catalog_item_id(
        self,
        catalog_item_id: uuid.UUID,
    ) -> InventoryItemProfile | None:
        return self.profiles.get(catalog_item_id)

    async def update(
        self,
        profile: InventoryItemProfile,
        **kwargs,
    ) -> InventoryItemProfile:
        for key, value in kwargs.items():
            setattr(profile, key, value)
        return profile


class FakeBusinessMembershipRepository:
    """In-memory membership repository."""

    def __init__(self, allowed_members: set[tuple[uuid.UUID, uuid.UUID]]) -> None:
        self.allowed_members = allowed_members

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (business_id, user_id) in self.allowed_members


class FakeCatalogUnitOfWork:
    """Fake unit of work for catalog operations."""

    def __init__(
        self,
        item_repo: FakeCatalogItemRepository,
        profile_repo: FakeInventoryItemProfileRepository,
        membership_repo: FakeBusinessMembershipRepository,
    ) -> None:
        self.catalog_items = item_repo
        self.inventory_profiles = profile_repo
        self.business_memberships = membership_repo
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def commit(self):
        self.committed = True


def build_test_user() -> IdentityUser:
    return IdentityUser(
        id=uuid.uuid4(),
        email="operator@example.com",
        first_name="Test",
        last_name="User",
        display_name="Test User",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )


def build_app(uow: FakeCatalogUnitOfWork, user: IdentityUser):
    app = create_app(initialize_resources=False)
    dispatcher = EventDispatcher()
    service = CatalogService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_catalog_unit_of_work] = lambda: uow
    app.dependency_overrides[get_catalog_service] = lambda: service
    return app, service, dispatcher


async def test_create_and_get_catalog_item_product():
    """Create a PRODUCT item and retrieve it."""
    business_id = uuid.uuid4()
    user = build_test_user()
    memberships = {(business_id, user.id)}
    uow = FakeCatalogUnitOfWork(
        FakeCatalogItemRepository(),
        FakeInventoryItemProfileRepository(),
        FakeBusinessMembershipRepository(memberships),
    )
    app, service, _ = build_app(uow, user)
    client = TestClient(app)

    payload = {
        "name": "Heavy Duty Router",
        "code": "RTR-001",
        "item_type": "product",
        "hsn_code": "847130",
        "gst_rate": "18.00",
        "selling_price": "2500.00",
        "default_unit": "PCS",
        "description": "Enterprise router",
        "stock_tracking": True,
        "legacy_product_id": str(uuid.uuid4()),
        "default_warehouse_id": str(uuid.uuid4()),
    }

    response = client.post(f"/api/v1/catalog/items?business_id={business_id}", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    item_id = data["id"]
    assert data["name"] == "Heavy Duty Router"
    assert data["item_type"] == "product"
    assert data["status"] == "active"
    assert data["inventory_profile"]["stock_tracking"] is True

    # Retrieve by ID
    get_res = client.get(f"/api/v1/catalog/items/{item_id}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == item_id


async def test_create_catalog_item_service():
    """Create a SERVICE item with SAC code."""
    business_id = uuid.uuid4()
    user = build_test_user()
    memberships = {(business_id, user.id)}
    uow = FakeCatalogUnitOfWork(
        FakeCatalogItemRepository(),
        FakeInventoryItemProfileRepository(),
        FakeBusinessMembershipRepository(memberships),
    )
    app, service, _ = build_app(uow, user)
    client = TestClient(app)

    payload = {
        "name": "Network Setup Service",
        "code": "SRV-NET-01",
        "item_type": "service",
        "sac_code": "998311",
        "gst_rate": "18.00",
        "selling_price": "5000.00",
        "default_unit": "HOURS",
    }

    response = client.post(f"/api/v1/catalog/items?business_id={business_id}", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["item_type"] == "service"
    assert data["inventory_profile"] is None


async def test_sec_01_cross_tenant_isolation_returns_uniform_404():
    """Accessing an item belonging to another business returns uniform 404."""
    business_a = uuid.uuid4()
    business_b = uuid.uuid4()
    user = build_test_user()
    # User is only member of Business A
    memberships = {(business_a, user.id)}
    uow = FakeCatalogUnitOfWork(
        FakeCatalogItemRepository(),
        FakeInventoryItemProfileRepository(),
        FakeBusinessMembershipRepository(memberships),
    )
    app, service, _ = build_app(uow, user)
    client = TestClient(app)

    # Pre-populate an item for business B
    item_b = await uow.catalog_items.create(
        CatalogItemCreate(
            name="Confidential Blueprint",
            code="B-001",
            item_type=ItemType.SERVICE,
            sac_code="998311",
            gst_rate=Decimal("18.00"),
            selling_price=Decimal("10000.00"),
            default_unit="PCS",
        ),
        business_id=business_b,
    )

    # User attempts to query Business B's item
    res = client.get(f"/api/v1/catalog/items/{item_b.id}")
    assert res.status_code == 404
    # Ensure error does not leak business_b id or name
    assert "Confidential Blueprint" not in res.text
    assert str(business_b) not in res.text


async def test_archive_and_restore_lifecycle():
    """Archiving and restoring a catalog item."""
    business_id = uuid.uuid4()
    user = build_test_user()
    memberships = {(business_id, user.id)}
    uow = FakeCatalogUnitOfWork(
        FakeCatalogItemRepository(),
        FakeInventoryItemProfileRepository(),
        FakeBusinessMembershipRepository(memberships),
    )
    app, service, _ = build_app(uow, user)
    client = TestClient(app)

    item = await uow.catalog_items.create(
        CatalogItemCreate(
            name="Discontinued Gadget",
            code="GAD-001",
            item_type=ItemType.PRODUCT,
            hsn_code="847130",
            gst_rate=Decimal("18.00"),
            selling_price=Decimal("100.00"),
            default_unit="PCS",
        ),
        business_id=business_id,
    )

    # Archive
    arch_res = client.post(f"/api/v1/catalog/items/{item.id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["data"]["status"] == "archived"

    # Restore
    rest_res = client.post(f"/api/v1/catalog/items/{item.id}/restore")
    assert rest_res.status_code == 200
    assert rest_res.json()["data"]["status"] == "active"


async def test_duplicate_code_conflict():
    """Creating an item with duplicate code in same business raises conflict."""
    business_id = uuid.uuid4()
    user = build_test_user()
    memberships = {(business_id, user.id)}
    uow = FakeCatalogUnitOfWork(
        FakeCatalogItemRepository(),
        FakeInventoryItemProfileRepository(),
        FakeBusinessMembershipRepository(memberships),
    )
    app, service, _ = build_app(uow, user)
    client = TestClient(app)

    payload = {
        "name": "Original",
        "code": "DUP-001",
        "item_type": "product",
        "hsn_code": "847130",
        "gst_rate": "18.00",
        "selling_price": "100.00",
        "default_unit": "PCS",
    }
    res1 = client.post(f"/api/v1/catalog/items?business_id={business_id}", json=payload)
    assert res1.status_code == 201

    res2 = client.post(f"/api/v1/catalog/items?business_id={business_id}", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.text
