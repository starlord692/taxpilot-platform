"""Document API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.config import get_settings
from app.core.database import database_state, initialize_database
from app.modules.documents.ocr import OCRProviderFactory
from app.modules.documents.services import (
    DocumentService,
    DocumentUnitOfWork,
    LocalStorageBackend,
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


def get_document_unit_of_work() -> object:
    """Provide document Unit of Work for authorization helpers."""
    return SQLAlchemyUnitOfWork(get_session_factory())


def get_document_service() -> DocumentService:
    """Provide document service."""
    settings = get_settings()
    session_factory = get_session_factory()
    languages = [
        language.strip()
        for language in settings.ocr_languages.split(",")
        if language.strip()
    ]
    return DocumentService(
        unit_of_work_factory=cast(
            Callable[[], DocumentUnitOfWork],
            lambda: SQLAlchemyUnitOfWork(session_factory),
        ),
        event_dispatcher=get_event_dispatcher(),
        storage=LocalStorageBackend(settings.document_storage_path),
        ocr_provider_factory=OCRProviderFactory(
            default_provider=settings.ocr_provider,
            languages=languages,
            tesseract_path=settings.tesseract_path,
            max_pages=settings.max_ocr_pages,
            timeout_seconds=settings.ocr_timeout,
        ),
        max_upload_size_bytes=settings.document_max_upload_size_bytes,
    )
