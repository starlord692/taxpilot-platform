"""Catalog application service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.catalog.events import (
    CatalogItemArchivedEvent,
    CatalogItemCreatedEvent,
    CatalogItemRestoredEvent,
    CatalogItemUpdatedEvent,
)
from app.modules.catalog.exceptions import (
    CatalogItemNotFoundException,
    DuplicateCatalogItemException,
)
from app.modules.catalog.models import CatalogItem, CatalogItemStatus, ItemType
from app.modules.catalog.schemas import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemResponse,
    CatalogItemUpdate,
)


class CatalogRepositoryProtocol(Protocol):
    async def create(
        self,
        request: CatalogItemCreate,
        *,
        business_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> CatalogItem: ...
    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None: ...
    async def get_by_code(
        self, business_id: uuid.UUID, code: str
    ) -> CatalogItem | None: ...
    async def update(
        self, item: CatalogItem, request: CatalogItemUpdate
    ) -> CatalogItem: ...
    async def list_items(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        item_type: ItemType | None = None,
        status: CatalogItemStatus | None = None,
    ) -> Page[CatalogItem]: ...


class CatalogUnitOfWork(Protocol):
    catalog_items: CatalogRepositoryProtocol

    async def __aenter__(self) -> "CatalogUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...
    async def commit(self) -> None: ...


class CatalogService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], CatalogUnitOfWork],
        event_dispatcher: EventDispatcher,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._events = event_dispatcher

    async def create(
        self, request: CatalogItemCreate, business_id: uuid.UUID
    ) -> CatalogItemResponse:
        validated = CatalogItemCreate.model_validate(request)
        async with self._uow_factory() as uow:
            if validated.code and await uow.catalog_items.get_by_code(
                business_id, validated.code
            ):
                raise DuplicateCatalogItemException(
                    "Catalog item code already exists", details={"code": validated.code}
                )
            item = await uow.catalog_items.create(validated, business_id=business_id)
            await self._events.dispatch(
                CatalogItemCreatedEvent(item.id, item.business_id)
            )
            await uow.commit()
        return CatalogItemResponse.model_validate(item)

    async def get(
        self, item_id: uuid.UUID, business_id: uuid.UUID
    ) -> CatalogItemResponse:
        async with self._uow_factory() as uow:
            item = await self._require(uow, item_id, business_id)
            await uow.commit()
        return CatalogItemResponse.model_validate(item)

    async def update(
        self, item_id: uuid.UUID, request: CatalogItemUpdate, business_id: uuid.UUID
    ) -> CatalogItemResponse:
        async with self._uow_factory() as uow:
            item = await self._require(uow, item_id, business_id)
            if request.code and request.code != item.code:
                duplicate = await uow.catalog_items.get_by_code(
                    business_id, request.code
                )
                if duplicate:
                    raise DuplicateCatalogItemException(
                        "Catalog item code already exists",
                        details={"code": request.code},
                    )
            item = await uow.catalog_items.update(item, request)
            await self._events.dispatch(
                CatalogItemUpdatedEvent(item.id, item.business_id)
            )
            await uow.commit()
        return CatalogItemResponse.model_validate(item)

    async def set_archived(
        self, item_id: uuid.UUID, business_id: uuid.UUID, archived: bool
    ) -> CatalogItemResponse:
        async with self._uow_factory() as uow:
            item = await self._require(uow, item_id, business_id)
            status = (
                CatalogItemStatus.ARCHIVED if archived else CatalogItemStatus.ACTIVE
            )
            item = await uow.catalog_items.update(
                item, CatalogItemUpdate(status=status)
            )
            event = CatalogItemArchivedEvent if archived else CatalogItemRestoredEvent
            await self._events.dispatch(event(item.id, item.business_id))
            await uow.commit()
        return CatalogItemResponse.model_validate(item)

    async def list(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
        item_type: ItemType | None = None,
        status: CatalogItemStatus | None = None,
    ) -> Page[CatalogItemListResponse]:
        async with self._uow_factory() as uow:
            page = await uow.catalog_items.list_items(
                business_id, pagination, item_type=item_type, status=status
            )
            await uow.commit()
        return Page.create(
            items=[CatalogItemListResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=pagination,
        )

    async def _require(
        self, uow: CatalogUnitOfWork, item_id: uuid.UUID, business_id: uuid.UUID
    ) -> CatalogItem:
        item = await uow.catalog_items.get_by_id(item_id)
        if item is None or item.business_id != business_id:
            raise CatalogItemNotFoundException(
                "Catalog item not found", details={"catalog_item_id": str(item_id)}
            )
        return item
