"""Business Understanding API dependencies."""

from collections.abc import Callable
from typing import cast

from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.modules.business.api.dependencies import get_session_factory
from app.modules.business_understanding.services import BusinessUnderstandingService
from app.modules.business_understanding.services.business_understanding_service import (
    BusinessUnderstandingUnitOfWork,
)


def get_business_understanding_service() -> BusinessUnderstandingService:
    """Provide the read-only service with the established Unit of Work."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], BusinessUnderstandingUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return BusinessUnderstandingService(unit_of_work_factory=unit_of_work_factory)
