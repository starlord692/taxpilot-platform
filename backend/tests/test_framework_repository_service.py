"""Tests for repository and service framework primitives."""

import uuid
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundException
from app.common.models.abstract import BaseEntity
from app.common.repositories import BaseRepository
from app.common.services import BaseService

pytestmark = pytest.mark.asyncio


class FrameworkEntity(BaseEntity):
    """Concrete test entity used by repository and service tests."""

    __tablename__ = "framework_entities"


def build_session_mock() -> AsyncSession:
    """Build a typed async session mock."""
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock()
    session.flush = AsyncMock()
    return cast(AsyncSession, session)


async def test_repository_add_flushes_entity() -> None:
    """Repository add attaches and flushes an entity."""
    session = build_session_mock()
    repository = BaseRepository(session, FrameworkEntity)
    entity = FrameworkEntity()

    result = await repository.add(entity)

    assert result is entity
    cast(Any, session.add).assert_called_once_with(entity)
    cast(Any, session.flush).assert_awaited_once()


async def test_repository_delete_soft_deletes_entity() -> None:
    """Repository delete marks an entity as deleted and flushes."""
    session = build_session_mock()
    repository = BaseRepository(session, FrameworkEntity)
    entity = FrameworkEntity()
    entity.is_deleted = False
    entity.deleted_at = None

    await repository.delete(entity)

    assert entity.is_deleted is True
    assert entity.deleted_at is not None
    cast(Any, session.add).assert_called_once_with(entity)
    cast(Any, session.flush).assert_awaited_once()


async def test_service_get_returns_entity() -> None:
    """Service returns an entity from its repository."""
    entity_id = uuid.uuid4()
    entity = FrameworkEntity()
    repository = Mock(spec=BaseRepository[FrameworkEntity])
    repository.get = AsyncMock(return_value=entity)
    service = BaseService(cast(BaseRepository[FrameworkEntity], repository))

    result = await service.get(entity_id)

    assert result is entity


async def test_service_get_raises_not_found() -> None:
    """Service raises framework not-found exceptions for missing entities."""
    repository = Mock(spec=BaseRepository[FrameworkEntity])
    repository.get = AsyncMock(return_value=None)
    service = BaseService(cast(BaseRepository[FrameworkEntity], repository))

    with pytest.raises(NotFoundException):
        await service.get(uuid.uuid4())
