"""Tests for Inventory Management API routers."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.inventory.api.dependencies import (
    get_inventory_service,
    get_inventory_unit_of_work,
    get_product_service,
    get_warehouse_service,
)
from app.modules.inventory.exceptions import DuplicateProductException
from app.modules.inventory.models import Product, Warehouse
from app.modules.inventory.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    StockBalanceListResponse,
    StockBalanceResponse,
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership result."""
        self.member = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership result."""
        _ = business_id
        _ = user_id
        return self.member


class FakeProductRepository:
    """Fake product repository for API authorization checks."""

    def __init__(self, product: Product | None) -> None:
        """Initialize with product."""
        self.product = product

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Return product by id."""
        if self.product is not None and self.product.id == product_id:
            return self.product
        return None


class FakeWarehouseRepository:
    """Fake warehouse repository for API authorization checks."""

    def __init__(self, warehouse: Warehouse | None) -> None:
        """Initialize with warehouse."""
        self.warehouse = warehouse

    async def get_by_id(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Return warehouse by id."""
        if self.warehouse is not None and self.warehouse.id == warehouse_id:
            return self.warehouse
        return None


class FakeInventoryUnitOfWork:
    """Fake Inventory Unit of Work for API tests."""

    def __init__(
        self,
        *,
        product: Product | None,
        warehouse: Warehouse | None,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.products = FakeProductRepository(product)
        self.warehouses = FakeWarehouseRepository(warehouse)
        self.business_memberships = FakeMembershipRepository(is_member=is_member)

    async def __aenter__(self) -> "FakeInventoryUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""


class FakeProductService:
    """Fake product service for API tests."""

    def __init__(self, product: ProductResponse) -> None:
        """Initialize with product response."""
        self.product = product
        self.created_request: ProductCreate | None = None
        self.updated_request: ProductUpdate | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None
        self.sku: str | None = None
        self.name: str | None = None
        self.category: str | None = None
        self.is_active: bool | None = None
        self.raise_duplicate = False

    async def create_product(
        self,
        request: ProductCreate,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return created product."""
        if self.raise_duplicate:
            raise DuplicateProductException("Product already exists")
        self.created_request = request
        self.business_id = business_id
        return self.product

    async def update_product(
        self,
        product_id: uuid.UUID,
        request: ProductUpdate,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return updated product."""
        _ = product_id
        self.updated_request = request
        self.business_id = business_id
        return self.product.model_copy(update=request.model_dump(exclude_unset=True))

    async def activate_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return activated product."""
        _ = product_id
        self.business_id = business_id
        return self.product.model_copy(update={"is_active": True})

    async def deactivate_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return deactivated product."""
        _ = product_id
        self.business_id = business_id
        return self.product.model_copy(update={"is_active": False})

    async def get_product(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> ProductResponse:
        """Return product."""
        _ = product_id
        self.business_id = business_id
        return self.product

    async def list_products(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        sku: str | None = None,
        name: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> Page[ProductListResponse]:
        """Return product page."""
        _ = sort
        self.business_id = business_id
        self.pagination = pagination or PaginationParams()
        self.sku = sku
        self.name = name
        self.category = category
        self.is_active = is_active
        return Page.create(
            items=[ProductListResponse.model_validate(self.product)],
            total=1,
            params=self.pagination,
        )


class FakeWarehouseService:
    """Fake warehouse service for API tests."""

    def __init__(self, warehouse: WarehouseResponse) -> None:
        """Initialize with warehouse response."""
        self.warehouse = warehouse
        self.created_request: WarehouseCreate | None = None
        self.updated_request: WarehouseUpdate | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None
        self.code: str | None = None
        self.name: str | None = None
        self.is_active: bool | None = None

    async def create_warehouse(
        self,
        request: WarehouseCreate,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return created warehouse."""
        self.created_request = request
        self.business_id = business_id
        return self.warehouse

    async def update_warehouse(
        self,
        warehouse_id: uuid.UUID,
        request: WarehouseUpdate,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return updated warehouse."""
        _ = warehouse_id
        self.updated_request = request
        self.business_id = business_id
        return self.warehouse.model_copy(update=request.model_dump(exclude_unset=True))

    async def activate_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return activated warehouse."""
        _ = warehouse_id
        self.business_id = business_id
        return self.warehouse.model_copy(update={"is_active": True})

    async def deactivate_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return deactivated warehouse."""
        _ = warehouse_id
        self.business_id = business_id
        return self.warehouse.model_copy(update={"is_active": False})

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> WarehouseResponse:
        """Return warehouse."""
        _ = warehouse_id
        self.business_id = business_id
        return self.warehouse

    async def list_warehouses(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> Page[WarehouseListResponse]:
        """Return warehouse page."""
        _ = sort
        self.business_id = business_id
        self.pagination = pagination or PaginationParams()
        self.code = code
        self.name = name
        self.is_active = is_active
        return Page.create(
            items=[WarehouseListResponse.model_validate(self.warehouse)],
            total=1,
            params=self.pagination,
        )


class FakeInventoryService:
    """Fake inventory read service for API tests."""

    def __init__(
        self,
        product: ProductResponse,
        balance: StockBalanceResponse,
    ) -> None:
        """Initialize with responses."""
        self.product = product
        self.balance = balance
        self.business_id: uuid.UUID | None = None
        self.query: str | None = None

    async def list_stock_balances(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return stock balance page."""
        _ = product_id
        _ = warehouse_id
        self.business_id = business_id
        return Page.create(
            items=[StockBalanceListResponse.model_validate(self.balance)],
            total=1,
            params=pagination or PaginationParams(),
        )

    async def get_product_stock(
        self,
        product_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> list[StockBalanceResponse]:
        """Return product stock."""
        _ = product_id
        self.business_id = business_id
        return [self.balance]

    async def get_warehouse_stock(
        self,
        warehouse_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[StockBalanceListResponse]:
        """Return warehouse stock."""
        _ = warehouse_id
        self.business_id = business_id
        return Page.create(
            items=[StockBalanceListResponse.model_validate(self.balance)],
            total=1,
            params=pagination or PaginationParams(),
        )

    async def search_inventory(
        self,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[ProductListResponse]:
        """Return inventory search results."""
        self.business_id = business_id
        self.query = query
        return Page.create(
            items=[ProductListResponse.model_validate(self.product)],
            total=1,
            params=pagination or PaginationParams(),
        )


def build_user() -> IdentityUser:
    """Build an authenticated identity user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
    )


def build_product_model(business_id: uuid.UUID) -> Product:
    """Build a product model."""
    return Product(
        id=uuid.uuid4(),
        business_id=business_id,
        sku="LAPTOP-001",
        name="Business Laptop",
        category="Hardware",
        unit_of_measure="pcs",
        purchase_price=Decimal("50000.00"),
        selling_price=Decimal("65000.00"),
        reorder_level=Decimal("5.0000"),
        is_active=True,
    )


def build_warehouse_model(business_id: uuid.UUID) -> Warehouse:
    """Build a warehouse model."""
    return Warehouse(
        id=uuid.uuid4(),
        business_id=business_id,
        code="MAIN",
        name="Main Warehouse",
        is_default=True,
        is_active=True,
    )


def build_balance_response(
    business_id: uuid.UUID,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
) -> StockBalanceResponse:
    """Build a stock balance response."""
    return StockBalanceResponse(
        id=uuid.uuid4(),
        business_id=business_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity_on_hand=Decimal("10.0000"),
        quantity_reserved=Decimal("0.0000"),
        quantity_available=Decimal("10.0000"),
        last_updated=datetime.now(tz=UTC),
    )


def build_client(
    *,
    is_authenticated: bool = True,
    is_member: bool = True,
    product_exists: bool = True,
    warehouse_exists: bool = True,
    duplicate_product: bool = False,
) -> tuple[
    TestClient,
    FakeProductService,
    FakeWarehouseService,
    FakeInventoryService,
    Product,
    Warehouse,
]:
    """Build a test client with dependency overrides."""
    business_id = uuid.uuid4()
    product = build_product_model(business_id)
    warehouse = build_warehouse_model(business_id)
    product_response = ProductResponse.model_validate(product)
    warehouse_response = WarehouseResponse.model_validate(warehouse)
    balance = build_balance_response(business_id, product.id, warehouse.id)
    product_service = FakeProductService(product_response)
    product_service.raise_duplicate = duplicate_product
    warehouse_service = FakeWarehouseService(warehouse_response)
    inventory_service = FakeInventoryService(product_response, balance)
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_inventory_unit_of_work] = (
        lambda: FakeInventoryUnitOfWork(
            product=product if product_exists else None,
            warehouse=warehouse if warehouse_exists else None,
            is_member=is_member,
        )
    )
    app.dependency_overrides[get_product_service] = lambda: product_service
    app.dependency_overrides[get_warehouse_service] = lambda: warehouse_service
    app.dependency_overrides[get_inventory_service] = lambda: inventory_service
    if is_authenticated:
        app.dependency_overrides[get_current_user] = build_user
    return (
        TestClient(app),
        product_service,
        warehouse_service,
        inventory_service,
        product,
        warehouse,
    )


def test_product_crud_endpoints() -> None:
    """Product API delegates CRUD operations to the service layer."""
    client, product_service, _warehouse_service, _inventory_service, product, _ = (
        build_client()
    )

    create_response = client.post(
        "/api/v1/inventory/products",
        params={"business_id": str(product.business_id)},
        json={
            "sku": "LAPTOP-001",
            "name": "Business Laptop",
            "unit_of_measure": "pcs",
            "purchase_price": "50000.00",
            "selling_price": "65000.00",
            "reorder_level": "5.0000",
        },
    )
    list_response = client.get(
        "/api/v1/inventory/products",
        params={
            "business_id": str(product.business_id),
            "page": 1,
            "page_size": 10,
            "sku": "LAPTOP-001",
            "name": "Laptop",
            "category": "Hardware",
            "active": True,
            "sort": "sku",
        },
    )
    get_response = client.get(f"/api/v1/inventory/products/{product.id}")
    patch_response = client.patch(
        f"/api/v1/inventory/products/{product.id}",
        json={"name": "Updated Laptop"},
    )
    activate_response = client.post(
        f"/api/v1/inventory/products/{product.id}/activate"
    )
    deactivate_response = client.post(
        f"/api/v1/inventory/products/{product.id}/deactivate"
    )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert activate_response.status_code == HTTP_OK
    assert deactivate_response.status_code == HTTP_OK
    assert product_service.pagination == PaginationParams(page=1, size=10)
    assert product_service.sku == "LAPTOP-001"
    assert product_service.is_active is True


def test_warehouse_crud_endpoints() -> None:
    """Warehouse API delegates CRUD operations to the service layer."""
    client, _product_service, warehouse_service, _inventory_service, _, warehouse = (
        build_client()
    )

    create_response = client.post(
        "/api/v1/inventory/warehouses",
        params={"business_id": str(warehouse.business_id)},
        json={"code": "MAIN", "name": "Main Warehouse", "is_default": True},
    )
    list_response = client.get(
        "/api/v1/inventory/warehouses",
        params={
            "business_id": str(warehouse.business_id),
            "code": "MAIN",
            "name": "Main",
            "active": True,
            "sort": "code",
        },
    )
    get_response = client.get(f"/api/v1/inventory/warehouses/{warehouse.id}")
    patch_response = client.patch(
        f"/api/v1/inventory/warehouses/{warehouse.id}",
        json={"name": "Updated Warehouse"},
    )
    activate_response = client.post(
        f"/api/v1/inventory/warehouses/{warehouse.id}/activate"
    )
    deactivate_response = client.post(
        f"/api/v1/inventory/warehouses/{warehouse.id}/deactivate"
    )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert activate_response.status_code == HTTP_OK
    assert deactivate_response.status_code == HTTP_OK
    assert warehouse_service.code == "MAIN"
    assert warehouse_service.is_active is True


def test_inventory_read_endpoints() -> None:
    """Inventory read endpoints return stock and search responses."""
    (
        client,
        _product_service,
        _warehouse_service,
        inventory_service,
        product,
        warehouse,
    ) = build_client()

    stock_response = client.get(
        "/api/v1/inventory/stock",
        params={
            "business_id": str(product.business_id),
            "product_id": str(product.id),
            "warehouse_id": str(warehouse.id),
            "movement_type": "purchase",
            "sort": "updated_at",
        },
    )
    product_stock_response = client.get(
        f"/api/v1/inventory/products/{product.id}/stock"
    )
    warehouse_stock_response = client.get(
        f"/api/v1/inventory/warehouses/{warehouse.id}/stock"
    )
    search_response = client.get(
        "/api/v1/inventory/search",
        params={"business_id": str(product.business_id), "query": "Laptop"},
    )

    assert stock_response.status_code == HTTP_OK
    assert product_stock_response.status_code == HTTP_OK
    assert warehouse_stock_response.status_code == HTTP_OK
    assert search_response.status_code == HTTP_OK
    assert inventory_service.query == "Laptop"


def test_inventory_authentication_and_authorization() -> None:
    """Inventory API requires authentication and business membership."""
    unauthenticated_client, *_ = build_client(is_authenticated=False)
    forbidden_client, *_ = build_client(is_member=False)

    unauthenticated_response = unauthenticated_client.get(
        "/api/v1/inventory/products",
        params={"business_id": str(uuid.uuid4())},
    )
    forbidden_response = forbidden_client.get(
        "/api/v1/inventory/products",
        params={"business_id": str(uuid.uuid4())},
    )

    assert unauthenticated_response.status_code == HTTP_UNAUTHORIZED
    assert forbidden_response.status_code == HTTP_FORBIDDEN


def test_inventory_not_found_and_conflict_errors() -> None:
    """Inventory API returns standardized 404 and 409 responses."""
    not_found_client, *_ = build_client(product_exists=False)
    conflict_client, *_ = build_client(duplicate_product=True)

    not_found_response = not_found_client.get(
        f"/api/v1/inventory/products/{uuid.uuid4()}"
    )
    conflict_response = conflict_client.post(
        "/api/v1/inventory/products",
        params={"business_id": str(uuid.uuid4())},
        json={
            "sku": "LAPTOP-001",
            "name": "Business Laptop",
            "unit_of_measure": "pcs",
        },
    )

    assert not_found_response.status_code == HTTP_NOT_FOUND
    assert conflict_response.status_code == HTTP_CONFLICT


def test_inventory_validation_errors_and_openapi() -> None:
    """Inventory API validates payloads and exposes OpenAPI paths."""
    client, *_ = build_client()

    response = client.post(
        "/api/v1/inventory/products",
        params={"business_id": str(uuid.uuid4())},
        json={"sku": "", "name": "Business Laptop", "unit_of_measure": "pcs"},
    )
    openapi = client.get("/openapi.json").json()

    assert response.status_code == HTTP_BAD_REQUEST
    assert "/api/v1/inventory/products" in openapi["paths"]
    assert "/api/v1/inventory/warehouses" in openapi["paths"]
    assert "/api/v1/inventory/stock" in openapi["paths"]
    assert "/api/v1/inventory/search" in openapi["paths"]
