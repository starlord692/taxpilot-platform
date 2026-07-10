"""Generic service foundation."""

import uuid

from app.common.exceptions import NotFoundException
from app.common.models.abstract import BaseEntity
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository


class BaseService[ModelT: BaseEntity]:
    """Reusable service base for future module services."""

    def __init__(self, repository: BaseRepository[ModelT]) -> None:
        """Initialize the service with its repository dependency."""
        self.repository = repository

    async def get(self, entity_id: uuid.UUID) -> ModelT:
        """Return an entity or raise if it does not exist."""
        entity = await self.repository.get(entity_id)
        if entity is None:
            raise NotFoundException("Resource not found")
        return entity

    async def list(self, pagination: PaginationParams | None = None) -> Page[ModelT]:
        """Return a paginated list of entities."""
        return await self.repository.list(pagination=pagination)

    async def create(self, entity: ModelT) -> ModelT:
        """Persist an entity through the repository."""
        return await self.repository.add(entity)

    async def delete(self, entity_id: uuid.UUID) -> None:
        """Delete an entity by identifier."""
        entity = await self.get(entity_id)
        await self.repository.delete(entity)
