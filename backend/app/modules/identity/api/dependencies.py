"""Identity API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.identity.services import AuthenticationService, RegistrationService
from app.modules.identity.services.authentication_service import (
    AuthenticationUnitOfWork,
)
from app.modules.identity.services.registration_service import RegistrationUnitOfWork


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


def get_registration_service() -> RegistrationService:
    """Provide the registration service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], RegistrationUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return RegistrationService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )


def get_authentication_service() -> AuthenticationService:
    """Provide the authentication service with injected dependencies."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], AuthenticationUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return AuthenticationService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
    )
