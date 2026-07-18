"""GST HSN and SAC code services."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.pagination import Page, PaginationParams
from app.modules.gst.exceptions import GSTCodeNotFoundException
from app.modules.gst.models import HSNCode, SACCode
from app.modules.gst.schemas import (
    HSNCodeCreate,
    HSNCodeResponse,
    HSNCodeUpdate,
    SACCodeCreate,
    SACCodeResponse,
    SACCodeUpdate,
)


class GSTCodeUnitOfWork(Protocol):
    """Unit of Work contract for GST code services."""

    hsn_codes: HSNCodePersistence
    sac_codes: SACCodePersistence

    async def __aenter__(self) -> GSTCodeUnitOfWork:
        """Enter transaction."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], GSTCodeUnitOfWork]


class HSNCodePersistence(Protocol):
    """Repository behavior required for HSN codes."""

    async def create(self, request: HSNCodeCreate) -> HSNCode:
        """Create HSN code."""
        ...

    async def update(self, code: HSNCode, request: HSNCodeUpdate) -> HSNCode:
        """Update HSN code."""
        ...

    async def get_by_id(self, code_id: uuid.UUID) -> HSNCode | None:
        """Return HSN code by UUID."""
        ...

    async def list(
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[HSNCode]:
        """List HSN codes."""
        ...


class SACCodePersistence(Protocol):
    """Repository behavior required for SAC codes."""

    async def create(self, request: SACCodeCreate) -> SACCode:
        """Create SAC code."""
        ...

    async def update(self, code: SACCode, request: SACCodeUpdate) -> SACCode:
        """Update SAC code."""
        ...

    async def get_by_id(self, code_id: uuid.UUID) -> SACCode | None:
        """Return SAC code by UUID."""
        ...

    async def list(
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[SACCode]:
        """List SAC codes."""
        ...


class GSTCodeService:
    """Coordinate HSN and SAC code CRUD workflows."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory

    async def create_hsn_code(self, request: HSNCodeCreate) -> HSNCodeResponse:
        """Create HSN code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.hsn_codes.create(HSNCodeCreate.model_validate(request))
            await uow.commit()
        return HSNCodeResponse.model_validate(code)

    async def update_hsn_code(
        self,
        code_id: uuid.UUID,
        request: HSNCodeUpdate,
    ) -> HSNCodeResponse:
        """Update HSN code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.hsn_codes.get_by_id(code_id)
            if code is None:
                raise GSTCodeNotFoundException("HSN code not found")
            code = await uow.hsn_codes.update(
                code,
                HSNCodeUpdate.model_validate(request),
            )
            await uow.commit()
        return HSNCodeResponse.model_validate(code)

    async def get_hsn_code(self, code_id: uuid.UUID) -> HSNCodeResponse:
        """Return HSN code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.hsn_codes.get_by_id(code_id)
            if code is None:
                raise GSTCodeNotFoundException("HSN code not found")
            await uow.commit()
        return HSNCodeResponse.model_validate(code)

    async def list_hsn_codes(
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[HSNCodeResponse]:
        """List HSN codes."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.hsn_codes.list(pagination)
            await uow.commit()
        return Page.create(
            items=[HSNCodeResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def create_sac_code(self, request: SACCodeCreate) -> SACCodeResponse:
        """Create SAC code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.sac_codes.create(SACCodeCreate.model_validate(request))
            await uow.commit()
        return SACCodeResponse.model_validate(code)

    async def update_sac_code(
        self,
        code_id: uuid.UUID,
        request: SACCodeUpdate,
    ) -> SACCodeResponse:
        """Update SAC code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.sac_codes.get_by_id(code_id)
            if code is None:
                raise GSTCodeNotFoundException("SAC code not found")
            code = await uow.sac_codes.update(
                code,
                SACCodeUpdate.model_validate(request),
            )
            await uow.commit()
        return SACCodeResponse.model_validate(code)

    async def get_sac_code(self, code_id: uuid.UUID) -> SACCodeResponse:
        """Return SAC code."""
        async with self._unit_of_work_factory() as uow:
            code = await uow.sac_codes.get_by_id(code_id)
            if code is None:
                raise GSTCodeNotFoundException("SAC code not found")
            await uow.commit()
        return SACCodeResponse.model_validate(code)

    async def list_sac_codes(
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[SACCodeResponse]:
        """List SAC codes."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.sac_codes.list(pagination)
            await uow.commit()
        return Page.create(
            items=[SACCodeResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )
