"""Catalog API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.catalog.service import CatalogService, CatalogUnitOfWork


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_event_dispatcher() -> EventDispatcher:
    """Provide an event dispatcher instance."""
    return EventDispatcher()


def get_catalog_unit_of_work() -> CatalogUnitOfWork:
    """Provide a Catalog Unit of Work."""
    session_factory = get_session_factory()
    return cast(CatalogUnitOfWork, SQLAlchemyUnitOfWork(session_factory))


def get_catalog_service() -> CatalogService:
    """Provide the Catalog service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], CatalogUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return CatalogService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )
