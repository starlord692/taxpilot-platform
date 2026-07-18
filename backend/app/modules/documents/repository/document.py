"""Document repositories."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.documents.models import (
    Document,
    DocumentPage,
    DocumentType,
    ExtractionStatus,
    OCRResult,
)


class DocumentRepository(BaseRepository[Document]):
    """Repository for document persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, Document)

    async def create(self, document: Document) -> Document:
        """Create a document record."""
        return await self.add(document)

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Return document by UUID."""
        result = await self.session.execute(
            self._base_statement().where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_checksum(
        self,
        *,
        business_id: uuid.UUID,
        checksum: str,
    ) -> Document | None:
        """Return document by business-scoped checksum."""
        result = await self.session.execute(
            self._base_statement().where(
                Document.business_id == business_id,
                Document.checksum == checksum,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        document_type: DocumentType | None = None,
        status: ExtractionStatus | None = None,
    ) -> Page[Document]:
        """List documents for a business."""
        statement = self._base_statement().where(Document.business_id == business_id)
        if document_type is not None:
            statement = statement.where(Document.document_type == document_type)
        if status is not None:
            statement = statement.where(Document.status == status)
        return await self._paginate(statement, pagination)

    async def update_status(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update document extraction status."""
        document.status = status
        self.session.add(document)
        await self.session.flush()
        return document

    async def update_processed(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update document status and processed timestamp."""
        document.status = status
        document.processed_at = utc_now()
        self.session.add(document)
        await self.session.flush()
        return document

    async def delete(self, document: Document) -> None:
        """Soft delete a document."""
        await super().delete(document)

    async def _paginate(
        self,
        statement: Select[tuple[Document]],
        pagination: PaginationParams | None,
    ) -> Page[Document]:
        """Paginate document rows."""
        params = pagination or PaginationParams()
        total_result = await self.session.execute(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=int(total_result.scalar_one()),
            params=params,
        )

    def _base_statement(self) -> Select[tuple[Document]]:
        """Return default document select."""
        return (
            select(Document)
            .options(
                selectinload(Document.pages),
                selectinload(Document.ocr_results),
            )
            .where(Document.is_deleted.is_(False))
            .order_by(Document.uploaded_at.desc())
        )


class DocumentPageRepository(BaseRepository[DocumentPage]):
    """Repository for document pages."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, DocumentPage)

    async def create(self, page: DocumentPage) -> DocumentPage:
        """Create a page record."""
        return await self.add(page)


class OCRResultRepository(BaseRepository[OCRResult]):
    """Repository for OCR result persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, OCRResult)

    async def create(self, result: OCRResult) -> OCRResult:
        """Create an OCR result."""
        return await self.add(result)

    async def list_by_document(self, document_id: uuid.UUID) -> list[OCRResult]:
        """Return OCR results for a document."""
        query_result = await self.session.execute(
            select(OCRResult)
            .where(
                OCRResult.document_id == document_id,
                OCRResult.is_deleted.is_(False),
            )
            .order_by(OCRResult.page_number.asc())
        )
        return list(query_result.scalars().all())
