"""GST API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.gst.services import (
    GSTCalculationService,
    GSTCodeService,
    GSTRegistrationService,
    GSTSettingsService,
    GSTTaxRateService,
)
from app.modules.gst.services.code_service import GSTCodeUnitOfWork
from app.modules.gst.services.registration_service import GSTRegistrationUnitOfWork
from app.modules.gst.services.settings_service import GSTSettingsUnitOfWork
from app.modules.gst.services.tax_rate_service import GSTTaxRateUnitOfWork


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


def get_gst_calculation_service() -> GSTCalculationService:
    """Provide the reusable GST calculation service."""
    return GSTCalculationService(event_dispatcher=get_event_dispatcher())


def get_gst_unit_of_work() -> object:
    """Provide GST Unit of Work for authorization helpers."""
    return SQLAlchemyUnitOfWork(get_session_factory())


def get_gst_registration_service() -> GSTRegistrationService:
    """Provide GST registration service."""
    session_factory = get_session_factory()
    return GSTRegistrationService(
        unit_of_work_factory=cast(
            Callable[[], GSTRegistrationUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
    )


def get_gst_tax_rate_service() -> GSTTaxRateService:
    """Provide GST tax rate service."""
    session_factory = get_session_factory()
    return GSTTaxRateService(
        unit_of_work_factory=cast(
            Callable[[], GSTTaxRateUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
    )


def get_gst_settings_service() -> GSTSettingsService:
    """Provide GST settings service."""
    session_factory = get_session_factory()
    return GSTSettingsService(
        unit_of_work_factory=cast(
            Callable[[], GSTSettingsUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
    )


def get_gst_code_service() -> GSTCodeService:
    """Provide GST code service."""
    session_factory = get_session_factory()
    return GSTCodeService(
        unit_of_work_factory=cast(
            Callable[[], GSTCodeUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        )
    )
