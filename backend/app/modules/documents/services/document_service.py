"""Document lifecycle and OCR service."""

import hashlib
import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.documents.events import (
    DocumentUploadedEvent,
    OCRCompletedEvent,
    OCRFailedEvent,
    OCRStartedEvent,
)
from app.modules.documents.exceptions import (
    DocumentNotFoundException,
    DocumentValidationException,
    DuplicateDocumentException,
    OCRProcessingException,
)
from app.modules.documents.models import (
    Document,
    DocumentPage,
    DocumentType,
    ExtractionStatus,
    OCRResult,
)
from app.modules.documents.ocr import OCRProviderFactory
from app.modules.documents.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    OCRProcessRequest,
)
from app.modules.documents.services.storage import StorageBackend

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/tiff",
}


class DocumentRepositoryProtocol(Protocol):
    """Repository behavior required for documents."""

    async def create(self, document: Document) -> Document:
        """Persist a document."""
        ...

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Return document by UUID."""
        ...

    async def get_by_checksum(
        self,
        *,
        business_id: uuid.UUID,
        checksum: str,
    ) -> Document | None:
        """Return document by checksum."""
        ...

    async def list_by_business(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        document_type: DocumentType | None = None,
        status: ExtractionStatus | None = None,
    ) -> Page[Document]:
        """List business documents."""
        ...

    async def update_status(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update document status."""
        ...

    async def update_processed(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update processed status and timestamp."""
        ...

    async def delete(self, document: Document) -> None:
        """Soft delete document."""
        ...


class DocumentPageRepositoryProtocol(Protocol):
    """Repository behavior required for document pages."""

    async def create(self, page: DocumentPage) -> DocumentPage:
        """Persist document page metadata."""
        ...


class OCRResultRepositoryProtocol(Protocol):
    """Repository behavior required for OCR results."""

    async def create(self, result: OCRResult) -> OCRResult:
        """Persist OCR result."""
        ...


class DocumentUnitOfWork(Protocol):
    """Unit of Work contract for document processing."""

    documents: DocumentRepositoryProtocol
    document_pages: DocumentPageRepositoryProtocol
    ocr_results: OCRResultRepositoryProtocol

    async def __aenter__(self) -> "DocumentUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], DocumentUnitOfWork]


class DocumentService:
    """Manage document upload, storage, lifecycle, and OCR metadata."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        storage: StorageBackend,
        ocr_provider_factory: OCRProviderFactory,
        max_upload_size_bytes: int,
        allowed_mime_types: set[str] | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._storage = storage
        self._ocr_provider_factory = ocr_provider_factory
        self._max_upload_size_bytes = max_upload_size_bytes
        self._allowed_mime_types = allowed_mime_types or ALLOWED_MIME_TYPES

    async def upload(
        self,
        request: DocumentUploadRequest,
        content: bytes,
    ) -> DocumentResponse:
        """Upload and persist document metadata."""
        self._validate_upload(request, content)
        checksum = hashlib.sha256(content).hexdigest()
        async with self._unit_of_work_factory() as uow:
            duplicate = await uow.documents.get_by_checksum(
                business_id=request.business_id,
                checksum=checksum,
            )
            if duplicate is not None:
                raise DuplicateDocumentException(
                    "Document checksum already exists for this business",
                    details={"document_id": str(duplicate.id)},
                )
            storage_path = await self._storage.save(
                business_id=request.business_id,
                filename=request.original_filename,
                content=content,
            )
            document = await uow.documents.create(
                Document(
                    business_id=request.business_id,
                    uploaded_by=request.uploaded_by,
                    original_filename=request.original_filename,
                    mime_type=request.mime_type,
                    file_size=len(content),
                    storage_path=storage_path,
                    checksum=checksum,
                    document_type=request.document_type,
                    status=ExtractionStatus.OCR_PENDING,
                    page_count=self._estimate_page_count(request, content),
                )
            )
            page = await uow.document_pages.create(
                DocumentPage(
                    document_id=document.id,
                    page_number=1,
                    storage_path=storage_path,
                )
            )
            document.pages.append(page)
            await self._event_dispatcher.dispatch(
                DocumentUploadedEvent(
                    document_id=document.id,
                    business_id=document.business_id,
                    uploaded_by=document.uploaded_by,
                )
            )
            await uow.commit()
            return DocumentResponse.model_validate(document)

    async def delete(self, document_id: uuid.UUID) -> None:
        """Soft delete document metadata and remove stored bytes."""
        async with self._unit_of_work_factory() as uow:
            document = await self._get_document(uow, document_id)
            await uow.documents.delete(document)
            await self._storage.delete(document.storage_path)
            await uow.commit()

    async def get(self, document_id: uuid.UUID) -> DocumentResponse:
        """Return document metadata."""
        async with self._unit_of_work_factory() as uow:
            document = await self._get_document(uow, document_id)
            await uow.commit()
            return DocumentResponse.model_validate(document)

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        document_type: DocumentType | None = None,
        status: ExtractionStatus | None = None,
    ) -> Page[DocumentListResponse]:
        """List business documents."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.documents.list_by_business(
                business_id=business_id,
                pagination=pagination,
                document_type=document_type,
                status=status,
            )
            await uow.commit()
        return Page.create(
            items=[
                DocumentListResponse.model_validate(document)
                for document in page.items
            ],
            total=page.meta.total,
            params=PaginationParams(page=page.meta.page, size=page.meta.size),
        )

    async def process_ocr(
        self,
        document_id: uuid.UUID,
        request: OCRProcessRequest,
    ) -> DocumentResponse:
        """Process OCR for an uploaded document."""
        async with self._unit_of_work_factory() as uow:
            document = await self._get_document(uow, document_id)
            provider = self._ocr_provider_factory.get(request.provider)
            await uow.documents.update_status(document, ExtractionStatus.OCR_RUNNING)
            await self._event_dispatcher.dispatch(
                OCRStartedEvent(
                    document_id=document.id,
                    business_id=document.business_id,
                    provider=provider.provider_name,
                )
            )
            try:
                content = await self._storage.read(document.storage_path)
                extraction = await provider.process(
                    content,
                    language=request.language,
                )
                result = await uow.ocr_results.create(
                    OCRResult(
                        document_id=document.id,
                        page_number=1,
                        provider=provider.provider_name,
                        language=extraction.language,
                        raw_text=extraction.raw_text,
                        confidence_score=extraction.confidence_score,
                        processing_time_ms=extraction.processing_time_ms,
                    )
                )
                document.ocr_results.append(result)
                await uow.documents.update_processed(
                    document,
                    ExtractionStatus.OCR_COMPLETED,
                )
                await self._event_dispatcher.dispatch(
                    OCRCompletedEvent(
                        document_id=document.id,
                        business_id=document.business_id,
                        provider=provider.provider_name,
                    )
                )
            except Exception as exc:
                await uow.documents.update_processed(
                    document,
                    ExtractionStatus.OCR_FAILED,
                )
                await self._event_dispatcher.dispatch(
                    OCRFailedEvent(
                        document_id=document.id,
                        business_id=document.business_id,
                        provider=provider.provider_name,
                        reason=str(exc),
                    )
                )
                raise OCRProcessingException(
                    "OCR processing failed",
                    details={"reason": str(exc)},
                ) from exc
            await uow.commit()
            return DocumentResponse.model_validate(document)

    async def reprocess_ocr(
        self,
        document_id: uuid.UUID,
        request: OCRProcessRequest,
    ) -> DocumentResponse:
        """Reprocess OCR for an existing document."""
        return await self.process_ocr(document_id, request)

    async def _get_document(
        self,
        uow: DocumentUnitOfWork,
        document_id: uuid.UUID,
    ) -> Document:
        """Return document or raise not found."""
        document = await uow.documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundException("Document was not found")
        return document

    def _validate_upload(
        self,
        request: DocumentUploadRequest,
        content: bytes,
    ) -> None:
        """Validate upload payload."""
        if not content:
            raise DocumentValidationException("Document content is required")
        if len(content) > self._max_upload_size_bytes:
            raise DocumentValidationException(
                "Document exceeds maximum upload size",
                details={
                    "max_upload_size_bytes": self._max_upload_size_bytes,
                    "file_size": len(content),
                },
            )
        if request.mime_type not in self._allowed_mime_types:
            raise DocumentValidationException(
                "Document MIME type is not allowed",
                details={"mime_type": request.mime_type},
            )

    def _estimate_page_count(
        self,
        request: DocumentUploadRequest,
        content: bytes,
    ) -> int:
        """Estimate page count without parsing document contents."""
        _ = self
        if request.mime_type == "application/pdf":
            return max(content.count(b"/Page"), 1)
        return 1
