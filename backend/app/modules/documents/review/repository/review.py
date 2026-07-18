"""Document review repositories."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.review.models import (
    DocumentReview,
    ReviewDecision,
    ReviewRevision,
    ReviewStatus,
    ValidationIssue,
)


class ValidationIssueRepository(BaseRepository[ValidationIssue]):
    """Repository for validation issues."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ValidationIssue)

    async def create(self, issue: ValidationIssue) -> ValidationIssue:
        """Create validation issue."""
        return await self.add(issue)

    async def list_by_document(self, document_id: uuid.UUID) -> list[ValidationIssue]:
        """Return validation issues for a document."""
        result = await self.session.execute(
            select(ValidationIssue)
            .where(
                ValidationIssue.document_id == document_id,
                ValidationIssue.is_deleted.is_(False),
            )
            .order_by(ValidationIssue.severity.asc())
        )
        return list(result.scalars().all())


class DocumentReviewRepository(BaseRepository[DocumentReview]):
    """Repository for document reviews."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, DocumentReview)

    async def create(self, review: DocumentReview) -> DocumentReview:
        """Create document review."""
        return await self.add(review)

    async def get_by_document_id(self, document_id: uuid.UUID) -> DocumentReview | None:
        """Return review by document UUID."""
        result = await self.session.execute(
            select(DocumentReview).where(
                DocumentReview.document_id == document_id,
                DocumentReview.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_pending(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[DocumentReview]:
        """Return pending reviews."""
        params = pagination or PaginationParams()
        filters = (
            ExtractedDocument.business_id == business_id,
            DocumentReview.review_status == ReviewStatus.PENDING,
            DocumentReview.is_deleted.is_(False),
            ExtractedDocument.is_deleted.is_(False),
        )
        statement = (
            select(DocumentReview)
            .join(
                ExtractedDocument,
                ExtractedDocument.document_id == DocumentReview.document_id,
            )
            .where(*filters)
            .order_by(DocumentReview.created_at.desc())
        )
        total_result = await self.session.execute(
            select(func.count(DocumentReview.id))
            .join(
                ExtractedDocument,
                ExtractedDocument.document_id == DocumentReview.document_id,
            )
            .where(*filters)
        )
        total = total_result.scalar_one()
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        items = list(result.scalars().all())
        return Page.create(items=items, total=total, params=params)


class ReviewRevisionRepository(BaseRepository[ReviewRevision]):
    """Repository for review revisions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ReviewRevision)

    async def create(self, revision: ReviewRevision) -> ReviewRevision:
        """Create review revision."""
        return await self.add(revision)

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewRevision]:
        """Return revisions for a document."""
        return await self._list_by_document(
            select(ReviewRevision).where(
                ReviewRevision.document_id == document_id,
                ReviewRevision.is_deleted.is_(False),
            )
        )

    async def _list_by_document(
        self,
        statement: Select[tuple[ReviewRevision]],
    ) -> list[ReviewRevision]:
        """Return revision rows."""
        result = await self.session.execute(statement)
        return list(result.scalars().all())


class ReviewDecisionRepository(BaseRepository[ReviewDecision]):
    """Repository for review decisions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ReviewDecision)

    async def create(self, decision: ReviewDecision) -> ReviewDecision:
        """Create review decision."""
        return await self.add(decision)

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewDecision]:
        """Return decisions for a document."""
        result = await self.session.execute(
            select(ReviewDecision).where(
                ReviewDecision.document_id == document_id,
                ReviewDecision.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())
