"""Document extraction API router."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.core.responses import SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.documents.extraction.api.dependencies import (
    get_document_extraction_service,
    get_extraction_unit_of_work,
)
from app.modules.documents.extraction.schemas import (
    ExtractDocumentRequest,
    ExtractedDocumentResponse,
)
from app.modules.documents.extraction.services import DocumentExtractionService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/documents", tags=["Document Extraction"])
ExtractionServiceDep = Annotated[
    DocumentExtractionService,
    Depends(get_document_extraction_service),
]
ExtractionUnitOfWorkDep = Annotated[Any, Depends(get_extraction_unit_of_work)]


@router.post(
    "/{document_id}/extract",
    response_model=SuccessResponse[ExtractedDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Extract document fields",
    description="Extracts structured business fields from existing OCR text.",
)
async def extract_document(
    document_id: uuid.UUID,
    request: ExtractDocumentRequest,
    current_user: CurrentUser,
    uow: ExtractionUnitOfWorkDep,
    service: ExtractionServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[ExtractedDocumentResponse]:
    """Extract document fields."""
    await _ensure_business_member(uow, business_id, current_user.id)
    extraction = await service.extract(document_id, request)
    _ensure_document_business(extraction.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document extraction completed successfully",
        data=extraction,
    )


@router.get(
    "/{document_id}/extraction",
    response_model=SuccessResponse[ExtractedDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document extraction",
    description="Returns structured extraction output for a document.",
)
async def get_document_extraction(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExtractionUnitOfWorkDep,
    service: ExtractionServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[ExtractedDocumentResponse]:
    """Return document extraction."""
    await _ensure_business_member(uow, business_id, current_user.id)
    extraction = await service.get(document_id)
    _ensure_document_business(extraction.business_id, business_id)
    return SuccessResponse(
        success=True,
        message="Document extraction returned successfully",
        data=extraction,
    )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when current user is not a business member."""
    async with uow:
        await ensure_active_business_membership(
            uow,
            business_id=business_id,
            user_id=user_id,
            entered=True,
        )


def _ensure_document_business(
    document_business_id: uuid.UUID,
    requested_business_id: uuid.UUID,
) -> None:
    """Raise when extraction does not belong to requested business."""
    if document_business_id != requested_business_id:
        raise BusinessNotMemberException(
            "Document extraction does not belong to the requested business",
            details={
                "document_business_id": str(document_business_id),
                "requested_business_id": str(requested_business_id),
            },
        )
