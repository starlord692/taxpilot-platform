"""Document extraction repositories."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.repositories import BaseRepository
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractionReview,
)


class ExtractedDocumentRepository(BaseRepository[ExtractedDocument]):
    """Repository for extracted document summaries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ExtractedDocument)

    async def create(self, extracted_document: ExtractedDocument) -> ExtractedDocument:
        """Create extracted document summary."""
        return await self.add(extracted_document)

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extraction summary by source document UUID."""
        result = await self.session.execute(
            self._base_statement().where(ExtractedDocument.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def delete_existing_for_document(self, document_id: uuid.UUID) -> None:
        """Soft-delete existing extraction output for a document."""
        existing = await self.get_by_document_id(document_id)
        if existing is not None:
            await self.delete(existing)

    def _base_statement(self) -> Select[tuple[ExtractedDocument]]:
        """Return default extraction select."""
        return (
            select(ExtractedDocument)
            .options(
                selectinload(ExtractedDocument.fields),
                selectinload(ExtractedDocument.reviews),
            )
            .where(ExtractedDocument.is_deleted.is_(False))
        )


class ExtractedFieldRepository(BaseRepository[ExtractedField]):
    """Repository for extracted fields."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ExtractedField)

    async def create(self, extracted_field: ExtractedField) -> ExtractedField:
        """Create extracted field."""
        return await self.add(extracted_field)


class ExtractionReviewRepository(BaseRepository[ExtractionReview]):
    """Repository for extraction reviews."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ExtractionReview)

    async def create(self, review: ExtractionReview) -> ExtractionReview:
        """Create extraction review."""
        return await self.add(review)
