"""GST HSN and SAC code repositories."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.gst.models import HSNCode, SACCode
from app.modules.gst.schemas import (
    HSNCodeCreate,
    HSNCodeUpdate,
    SACCodeCreate,
    SACCodeUpdate,
)


class HSNCodeRepository(BaseRepository[HSNCode]):
    """Repository for HSN code persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, HSNCode)

    async def create(self, request: HSNCodeCreate) -> HSNCode:
        """Create an HSN code."""
        return await self.add(HSNCode(**request.model_dump()))

    async def update(self, code: HSNCode, request: HSNCodeUpdate) -> HSNCode:
        """Update an HSN code."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(code, field_name, value)
        self.session.add(code)
        await self.session.flush()
        return code

    async def get_by_id(self, code_id: uuid.UUID) -> HSNCode | None:
        """Return HSN code by UUID."""
        result = await self.session.execute(
            self._base_statement().where(HSNCode.id == code_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> HSNCode | None:
        """Return HSN code by code."""
        result = await self.session.execute(
            self._base_statement().where(HSNCode.code == code)
        )
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[HSNCode]:
        """List HSN codes."""
        return await _paginate(
            self.session,
            self._base_statement().order_by(HSNCode.code.asc()),
            pagination,
        )

    def _base_statement(self) -> Select[tuple[HSNCode]]:
        """Return default select."""
        return select(HSNCode).where(HSNCode.is_deleted.is_(False))


class SACCodeRepository(BaseRepository[SACCode]):
    """Repository for SAC code persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, SACCode)

    async def create(self, request: SACCodeCreate) -> SACCode:
        """Create a SAC code."""
        return await self.add(SACCode(**request.model_dump()))

    async def update(self, code: SACCode, request: SACCodeUpdate) -> SACCode:
        """Update a SAC code."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(code, field_name, value)
        self.session.add(code)
        await self.session.flush()
        return code

    async def get_by_id(self, code_id: uuid.UUID) -> SACCode | None:
        """Return SAC code by UUID."""
        result = await self.session.execute(
            self._base_statement().where(SACCode.id == code_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> SACCode | None:
        """Return SAC code by code."""
        result = await self.session.execute(
            self._base_statement().where(SACCode.code == code)
        )
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        pagination: PaginationParams | None = None,
    ) -> Page[SACCode]:
        """List SAC codes."""
        return await _paginate(
            self.session,
            self._base_statement().order_by(SACCode.code.asc()),
            pagination,
        )

    def _base_statement(self) -> Select[tuple[SACCode]]:
        """Return default select."""
        return select(SACCode).where(SACCode.is_deleted.is_(False))


async def _paginate[T](
    session: AsyncSession,
    statement: Select[tuple[T]],
    pagination: PaginationParams | None,
) -> Page[T]:
    """Paginate a selectable statement."""
    params = pagination or PaginationParams()
    total_result = await session.execute(
        select(func.count()).select_from(statement.subquery())
    )
    result = await session.execute(statement.offset(params.offset).limit(params.limit))
    return Page.create(
        items=list(result.scalars().all()),
        total=int(total_result.scalar_one()),
        params=params,
    )
