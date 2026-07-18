"""Document Processing API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Query, Response, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.documents.api.dependencies import (
    get_document_service,
    get_document_unit_of_work,
)
from app.modules.documents.models import DocumentType, ExtractionStatus
from app.modules.documents.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    OCRProcessRequest,
)
from app.modules.documents.services import DocumentService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/documents", tags=["Documents"])
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
DocumentUnitOfWorkDep = Annotated[Any, Depends(get_document_unit_of_work)]


@router.post(
    "/upload",
    response_model=SuccessResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Uploads a document as raw bytes with document metadata.",
    responses={
        HTTPStatus.CREATED: {"description": "Document uploaded."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def upload_document(
    content: Annotated[bytes, Body(media_type="application/octet-stream")],
    current_user: CurrentUser,
    uow: DocumentUnitOfWorkDep,
    service: DocumentServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    mime_type: Annotated[
        str | None,
        Header(alias="Content-Type", description="Uploaded file MIME type."),
    ] = None,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> SuccessResponse[DocumentResponse]:
    """Upload document bytes."""
    await _ensure_business_member(uow, business_id, current_user.id)
    document = await service.upload(
        DocumentUploadRequest(
            business_id=business_id,
            uploaded_by=current_user.id,
            original_filename=filename,
            mime_type=mime_type or "application/octet-stream",
            document_type=document_type,
        ),
        content,
    )
    return SuccessResponse(
        success=True,
        message="Document uploaded successfully",
        data=document,
    )


@router.post(
    "/{document_id}/ocr",
    response_model=SuccessResponse[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Process document OCR",
    description="Runs OCR for an uploaded document using a configured provider.",
)
async def process_ocr(
    document_id: uuid.UUID,
    request: OCRProcessRequest,
    current_user: CurrentUser,
    uow: DocumentUnitOfWorkDep,
    service: DocumentServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[DocumentResponse]:
    """Process document OCR."""
    await _ensure_business_member(uow, business_id, current_user.id)
    document = await service.process_ocr(document_id, request)
    _ensure_document_business(document.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document OCR completed successfully",
        data=document,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[DocumentListResponse],
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="Lists uploaded documents for a business.",
)
async def list_documents(
    current_user: CurrentUser,
    uow: DocumentUnitOfWorkDep,
    service: DocumentServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    document_type: DocumentType | None = None,
    status_filter: ExtractionStatus | None = None,
) -> PaginatedApiResponse[DocumentListResponse]:
    """List documents."""
    await _ensure_business_member(uow, business_id, current_user.id)
    result = await service.list(
        business_id=business_id,
        pagination=PaginationParams(page=page, size=page_size),
        document_type=document_type,
        status=status_filter,
    )
    return PaginatedApiResponse(
        success=True,
        message="Documents returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.get(
    "/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document",
    description="Returns document metadata and OCR results.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: DocumentUnitOfWorkDep,
    service: DocumentServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[DocumentResponse]:
    """Get document."""
    await _ensure_business_member(uow, business_id, current_user.id)
    document = await service.get(document_id)
    _ensure_document_business(document.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document returned successfully",
        data=document,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Soft deletes document metadata and removes local stored bytes.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: DocumentUnitOfWorkDep,
    service: DocumentServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> Response:
    """Delete document."""
    await _ensure_business_member(uow, business_id, current_user.id)
    document = await service.get(document_id)
    _ensure_document_business(document.business_id, business_id)
    await service.delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when current user is not a business member."""
    async with uow:
        if not await uow.business_memberships.is_member(
            business_id=business_id,
            user_id=user_id,
        ):
            raise BusinessNotMemberException(
                "User is not a member of the business",
                details={"business_id": str(business_id), "user_id": str(user_id)},
            )


def _ensure_document_business(
    document_business_id: uuid.UUID,
    requested_business_id: uuid.UUID,
) -> None:
    """Raise when document does not belong to requested business."""
    if document_business_id != requested_business_id:
        raise BusinessNotMemberException(
            "Document does not belong to the requested business",
            details={
                "document_business_id": str(document_business_id),
                "requested_business_id": str(requested_business_id),
            },
        )
