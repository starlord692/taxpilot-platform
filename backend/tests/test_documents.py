"""Tests for Intelligent Document Processing foundation."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.documents.api.dependencies import (
    get_document_service,
    get_document_unit_of_work,
)
from app.modules.documents.events import (
    DocumentUploadedEvent,
    OCRCompletedEvent,
    OCRFailedEvent,
    OCRStartedEvent,
)
from app.modules.documents.exceptions import (
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
from app.modules.documents.ocr import OCRProvider, OCRProviderFactory
from app.modules.documents.ocr.interface import OCRExtraction
from app.modules.documents.schemas import DocumentUploadRequest, OCRProcessRequest
from app.modules.documents.services import DocumentService, DocumentUnitOfWork
from app.modules.documents.services.storage import StorageBackend
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

HTTP_CREATED = 201
HTTP_FORBIDDEN = 403
HTTP_NO_CONTENT = 204
HTTP_OK = 200


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture dispatched event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeStorage(StorageBackend):
    """In-memory document storage."""

    def __init__(self) -> None:
        """Initialize in-memory files."""
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def save(
        self,
        *,
        business_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> str:
        """Save bytes in memory."""
        path = f"memory://{business_id}/{filename}"
        self.files[path] = content
        return path

    async def delete(self, storage_path: str) -> None:
        """Delete bytes from memory."""
        self.files.pop(storage_path, None)
        self.deleted.append(storage_path)

    async def read(self, storage_path: str) -> bytes:
        """Read bytes from memory."""
        return self.files[storage_path]


class FailingOCRProvider(OCRProvider):
    """OCR provider that fails extraction."""

    provider_name = "failing"

    async def extract_text(self, content: bytes, *, language: str | None) -> str:
        """Fail text extraction."""
        _ = content
        _ = language
        raise RuntimeError("ocr unavailable")

    async def detect_language(self, text: str) -> str | None:
        """Detect language."""
        _ = text
        return None

    async def get_confidence(self, text: str) -> Decimal:
        """Return confidence."""
        _ = text
        return Decimal("0.00")


class FakeOCRProvider(OCRProvider):
    """OCR provider used for service tests."""

    def __init__(self, provider_name: str) -> None:
        """Initialize fake provider name."""
        self.provider_name = provider_name

    async def extract_text(self, content: bytes, *, language: str | None) -> str:
        """Extract text from bytes."""
        _ = language
        return content.decode("utf-8", errors="ignore").strip()

    async def detect_language(self, text: str) -> str | None:
        """Detect language."""
        return "eng" if text else None

    async def get_confidence(self, text: str) -> Decimal:
        """Return confidence."""
        return Decimal("90.00") if text else Decimal("0.00")

    async def process(
        self,
        content: bytes,
        *,
        language: str | None,
    ) -> OCRExtraction:
        """Process OCR for service tests."""
        raw_text = await self.extract_text(content, language=language)
        return OCRExtraction(
            raw_text=raw_text,
            language=language or "eng",
            confidence_score=Decimal("90.00") if raw_text else Decimal("0.00"),
            processing_time_ms=1,
        )


class FakeOCRProviderFactory(OCRProviderFactory):
    """OCR provider factory with injectable failure."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize provider state."""
        super().__init__()
        self.fail = fail

    def get(self, provider_name: str) -> OCRProvider:
        """Return configured provider."""
        _ = provider_name
        if self.fail:
            return FailingOCRProvider()
        return FakeOCRProvider(provider_name)


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership response."""
        self.is_member_result = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership response."""
        _ = business_id
        _ = user_id
        return self.is_member_result


@dataclass
class FakeDocumentRepository:
    """In-memory document repository."""

    documents: list[Document] = field(default_factory=list)

    async def create(self, document: Document) -> Document:
        """Create document."""
        if document.id is None:
            document.id = uuid.uuid4()
        if document.uploaded_at is None:
            document.uploaded_at = utc_now()
        self.documents.append(document)
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Return document by UUID."""
        return next(
            (
                document
                for document in self.documents
                if document.id == document_id and not document.is_deleted
            ),
            None,
        )

    async def get_by_checksum(
        self,
        *,
        business_id: uuid.UUID,
        checksum: str,
    ) -> Document | None:
        """Return document by checksum."""
        return next(
            (
                document
                for document in self.documents
                if document.business_id == business_id
                and document.checksum == checksum
                and not document.is_deleted
            ),
            None,
        )

    async def list_by_business(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        document_type: DocumentType | None = None,
        status: ExtractionStatus | None = None,
    ) -> Page[Document]:
        """List documents by business."""
        params = pagination or PaginationParams()
        items = [
            document
            for document in self.documents
            if document.business_id == business_id and not document.is_deleted
        ]
        if document_type is not None:
            items = [
                document
                for document in items
                if document.document_type == document_type
            ]
        if status is not None:
            items = [document for document in items if document.status == status]
        return Page.create(
            items=items[params.offset : params.offset + params.limit],
            total=len(items),
            params=params,
        )

    async def update_status(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update status."""
        document.status = status
        return document

    async def update_processed(
        self,
        document: Document,
        status: ExtractionStatus,
    ) -> Document:
        """Update processed status."""
        document.status = status
        return document

    async def delete(self, document: Document) -> None:
        """Soft delete document."""
        document.mark_deleted()


@dataclass
class FakeDocumentPageRepository:
    """In-memory document page repository."""

    pages: list[DocumentPage] = field(default_factory=list)

    async def create(self, page: DocumentPage) -> DocumentPage:
        """Create page."""
        if page.id is None:
            page.id = uuid.uuid4()
        self.pages.append(page)
        return page


@dataclass
class FakeOCRResultRepository:
    """In-memory OCR result repository."""

    results: list[OCRResult] = field(default_factory=list)

    async def create(self, result: OCRResult) -> OCRResult:
        """Create OCR result."""
        if result.id is None:
            result.id = uuid.uuid4()
        self.results.append(result)
        return result


class FakeDocumentUnitOfWork:
    """Fake Unit of Work for document tests."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize fake repositories."""
        self.documents = FakeDocumentRepository()
        self.document_pages = FakeDocumentPageRepository()
        self.ocr_results = FakeOCRResultRepository()
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter transaction."""
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback fake transaction on exception or missing commit."""
        _ = exc
        _ = traceback
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_user() -> IdentityUser:
    """Build authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Aarav",
        last_name="Sharma",
        display_name="Aarav Sharma",
        status=UserStatus.ACTIVE,
    )


def build_service_state(
    *,
    is_member: bool = True,
    fail_ocr: bool = False,
    max_upload_size_bytes: int = 1024,
) -> tuple[
    uuid.UUID,
    FakeDocumentUnitOfWork,
    FakeStorage,
    DocumentService,
    CapturingEventDispatcher,
]:
    """Build service and fake dependencies."""
    business_id = uuid.uuid4()
    uow = FakeDocumentUnitOfWork(is_member=is_member)
    storage = FakeStorage()
    dispatcher = CapturingEventDispatcher()
    service = DocumentService(
        unit_of_work_factory=lambda: cast(DocumentUnitOfWork, uow),
        event_dispatcher=dispatcher,
        storage=storage,
        ocr_provider_factory=FakeOCRProviderFactory(fail=fail_ocr),
        max_upload_size_bytes=max_upload_size_bytes,
    )
    return business_id, uow, storage, service, dispatcher


async def upload_sample(
    service: DocumentService,
    *,
    business_id: uuid.UUID,
    content: bytes = b"invoice text",
) -> uuid.UUID:
    """Upload sample document and return its UUID."""
    response = await service.upload(
        DocumentUploadRequest(
            business_id=business_id,
            uploaded_by=uuid.uuid4(),
            original_filename="invoice.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.SALES_INVOICE,
        ),
        content,
    )
    return response.id


@pytest.mark.asyncio
async def test_upload_document_and_duplicate_checksum() -> None:
    """Documents upload and duplicate checks work."""
    business_id, uow, storage, service, dispatcher = build_service_state()
    document_id = await upload_sample(service, business_id=business_id)

    assert document_id
    assert uow.documents.documents[0].status == ExtractionStatus.OCR_PENDING
    assert storage.files
    assert isinstance(dispatcher.events[0], DocumentUploadedEvent)

    with pytest.raises(DuplicateDocumentException):
        await upload_sample(service, business_id=business_id)


@pytest.mark.asyncio
async def test_invalid_and_large_files_rejected() -> None:
    """Invalid MIME types and oversized files are rejected."""
    business_id, _uow, _storage, service, _dispatcher = build_service_state(
        max_upload_size_bytes=4
    )
    request = DocumentUploadRequest(
        business_id=business_id,
        uploaded_by=uuid.uuid4(),
        original_filename="malware.exe",
        mime_type="application/octet-stream",
    )

    with pytest.raises(DocumentValidationException):
        await service.upload(request, b"abc")

    request.mime_type = "application/pdf"
    with pytest.raises(DocumentValidationException):
        await service.upload(request, b"abcde")


@pytest.mark.asyncio
async def test_process_ocr_and_provider_selection() -> None:
    """OCR processing stores extraction metadata."""
    business_id, uow, _storage, service, dispatcher = build_service_state()
    document_id = await upload_sample(
        service,
        business_id=business_id,
        content=b"hello taxpilot",
    )

    response = await service.process_ocr(
        document_id,
        OCRProcessRequest(provider="easyocr"),
    )

    assert response.status == ExtractionStatus.OCR_COMPLETED
    assert response.ocr_results[0].provider == "easyocr"
    assert response.ocr_results[0].raw_text == "hello taxpilot"
    assert uow.ocr_results.results[0].confidence_score == Decimal("90.00")
    assert any(isinstance(event, OCRStartedEvent) for event in dispatcher.events)
    assert any(isinstance(event, OCRCompletedEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_ocr_failure_rolls_back_and_publishes_failure() -> None:
    """OCR provider failures are wrapped and rolled back."""
    business_id, uow, _storage, service, dispatcher = build_service_state(
        fail_ocr=True
    )
    document_id = await upload_sample(service, business_id=business_id)

    with pytest.raises(OCRProcessingException):
        await service.process_ocr(document_id, OCRProcessRequest(provider="tesseract"))

    assert uow.rolled_back is True
    assert any(isinstance(event, OCRFailedEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_list_get_delete_and_business_isolation() -> None:
    """Document listing, retrieval, deletion, and isolation work."""
    business_id, _uow, storage, service, _dispatcher = build_service_state()
    document_id = await upload_sample(service, business_id=business_id)

    page = await service.list(business_id=business_id)
    document = await service.get(document_id)
    await service.delete(document_id)

    assert page.meta.total == 1
    assert document.business_id == business_id
    assert storage.deleted


def test_documents_api() -> None:
    """Document API exposes upload, OCR, list, get, and delete endpoints."""
    app = create_app(initialize_resources=False)
    business_id, uow, _storage, service, _dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_document_unit_of_work] = lambda: uow
    app.dependency_overrides[get_document_service] = lambda: service

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/v1/documents/upload",
            params={
                "business_id": str(business_id),
                "filename": "invoice.pdf",
                "document_type": DocumentType.SALES_INVOICE,
            },
            content=b"invoice text",
            headers={"Content-Type": "application/pdf"},
        )
        document_id = upload_response.json()["data"]["id"]
        ocr_response = client.post(
            f"/api/v1/documents/{document_id}/ocr",
            params={"business_id": str(business_id)},
            json={"provider": "tesseract"},
        )
        list_response = client.get(
            "/api/v1/documents",
            params={"business_id": str(business_id)},
        )
        get_response = client.get(
            f"/api/v1/documents/{document_id}",
            params={"business_id": str(business_id)},
        )
        delete_response = client.delete(
            f"/api/v1/documents/{document_id}",
            params={"business_id": str(business_id)},
        )
        schema = client.get("/openapi.json").json()

    assert upload_response.status_code == HTTP_CREATED
    assert ocr_response.status_code == HTTP_OK
    assert list_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert delete_response.status_code == HTTP_NO_CONTENT
    assert "/api/v1/documents/upload" in schema["paths"]
    assert "/api/v1/documents/{document_id}/ocr" in schema["paths"]

    denied_business_id, denied_uow, _denied_storage, denied_service, _events = (
        build_service_state(is_member=False)
    )
    app.dependency_overrides[get_document_unit_of_work] = lambda: denied_uow
    app.dependency_overrides[get_document_service] = lambda: denied_service

    with TestClient(app) as client:
        denied_response = client.get(
            "/api/v1/documents",
            params={"business_id": str(denied_business_id)},
        )

    assert denied_response.status_code == HTTP_FORBIDDEN
