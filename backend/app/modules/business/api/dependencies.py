"""Business API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.business.services import BusinessService
from app.modules.business.services.business_service import BusinessUnitOfWork


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


def get_business_service() -> BusinessService:
    """Provide the business service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], BusinessUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return BusinessService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )
