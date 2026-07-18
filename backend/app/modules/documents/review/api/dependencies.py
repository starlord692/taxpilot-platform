"""Document review API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.documents.review.services import (
    DocumentReviewService,
    ReviewUnitOfWork,
)


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_event_dispatcher() -> EventDispatcher:
    """Provide an event dispatcher."""
    return EventDispatcher()


def get_review_unit_of_work() -> object:
    """Provide review Unit of Work for authorization helpers."""
    return SQLAlchemyUnitOfWork(get_session_factory())


def get_document_review_service() -> DocumentReviewService:
    """Provide document review service."""
    session_factory = get_session_factory()
    return DocumentReviewService(
        unit_of_work_factory=cast(
            Callable[[], ReviewUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
    )
