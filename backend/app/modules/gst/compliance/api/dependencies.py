"""GST compliance API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.gst.compliance.services.compliance_service import (
    GSTComplianceUnitOfWork,
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


def get_gst_compliance_unit_of_work() -> object:
    """Provide Unit of Work for compliance authorization."""
    return SQLAlchemyUnitOfWork(get_session_factory())


def get_gst_compliance_service() -> GSTComplianceService:
    """Provide GST Compliance Engine service."""
    session_factory = get_session_factory()
    return GSTComplianceService(
        unit_of_work_factory=cast(
            Callable[[], GSTComplianceUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
    )
