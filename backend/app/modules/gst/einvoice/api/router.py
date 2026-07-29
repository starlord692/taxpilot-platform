"""E-invoicing and e-way bill API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.gst.einvoice.api.dependencies import (
    get_einvoice_service,
    get_einvoice_unit_of_work,
)
from app.modules.gst.einvoice.schemas import (
    EInvoiceCancelRequest,
    EInvoiceGenerateRequest,
    EInvoiceResponse,
    EInvoiceStatusResponse,
    EWayBillCancelRequest,
    EWayBillGenerateRequest,
    EWayBillResponse,
)
from app.modules.gst.einvoice.services import EInvoiceService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(tags=["GST E-Invoicing"])
EInvoiceServiceDep = Annotated[EInvoiceService, Depends(get_einvoice_service)]
EInvoiceUnitOfWorkDep = Annotated[Any, Depends(get_einvoice_unit_of_work)]


@router.post(
    "/einvoice/generate",
    response_model=SuccessResponse[EInvoiceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate IRN",
    description="Generates an IRN for an eligible posted sales invoice.",
    responses={
        HTTPStatus.CREATED: {"description": "IRN generated."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def generate_irn(
    request: EInvoiceGenerateRequest,
    current_user: CurrentUser,
    uow: EInvoiceUnitOfWorkDep,
    service: EInvoiceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[EInvoiceResponse]:
    """Generate IRN."""
    await _ensure_business_member(uow, business_id, current_user.id)
    await _ensure_invoice_business(uow, request.invoice_id, business_id)
    result = await service.generate_irn(request)
    return SuccessResponse(
        success=True,
        message="IRN generated successfully",
        data=result,
    )


@router.post(
    "/einvoice/cancel",
    response_model=SuccessResponse[EInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel IRN",
    description="Cancels an active IRN using the configured GST provider.",
)
async def cancel_irn(
    request: EInvoiceCancelRequest,
    current_user: CurrentUser,
    uow: EInvoiceUnitOfWorkDep,
    service: EInvoiceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[EInvoiceResponse]:
    """Cancel IRN."""
    await _ensure_business_member(uow, business_id, current_user.id)
    await _ensure_invoice_business(uow, request.invoice_id, business_id)
    result = await service.cancel_irn(request)
    return SuccessResponse(
        success=True,
        message="IRN cancelled successfully",
        data=result,
    )


@router.post(
    "/ewaybill/generate",
    response_model=SuccessResponse[EWayBillResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate e-way bill",
    description="Generates an e-way bill for an invoice with an active IRN.",
)
async def generate_eway_bill(
    request: EWayBillGenerateRequest,
    current_user: CurrentUser,
    uow: EInvoiceUnitOfWorkDep,
    service: EInvoiceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[EWayBillResponse]:
    """Generate e-way bill."""
    await _ensure_business_member(uow, business_id, current_user.id)
    await _ensure_invoice_business(uow, request.invoice_id, business_id)
    result = await service.generate_eway_bill(request)
    return SuccessResponse(
        success=True,
        message="E-way bill generated successfully",
        data=result,
    )


@router.post(
    "/ewaybill/cancel",
    response_model=SuccessResponse[EWayBillResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel e-way bill",
    description="Cancels an active e-way bill.",
)
async def cancel_eway_bill(
    request: EWayBillCancelRequest,
    current_user: CurrentUser,
    uow: EInvoiceUnitOfWorkDep,
    service: EInvoiceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[EWayBillResponse]:
    """Cancel e-way bill."""
    await _ensure_business_member(uow, business_id, current_user.id)
    await _ensure_invoice_business(uow, request.invoice_id, business_id)
    result = await service.cancel_eway_bill(request)
    return SuccessResponse(
        success=True,
        message="E-way bill cancelled successfully",
        data=result,
    )


@router.get(
    "/einvoice/{invoice_id}",
    response_model=SuccessResponse[EInvoiceStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get e-invoice status",
    description="Returns stored e-invoice, QR, e-way bill, and provider status.",
)
async def get_status(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: EInvoiceUnitOfWorkDep,
    service: EInvoiceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[EInvoiceStatusResponse]:
    """Return e-invoice status."""
    await _ensure_business_member(uow, business_id, current_user.id)
    await _ensure_invoice_business(uow, invoice_id, business_id)
    result = await service.get_status(invoice_id)
    return SuccessResponse(
        success=True,
        message="E-invoice status returned successfully",
        data=result,
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


async def _ensure_invoice_business(
    uow: Any,
    invoice_id: uuid.UUID,
    business_id: uuid.UUID,
) -> None:
    """Raise when an invoice does not belong to the resolved business."""
    async with uow:
        invoice = await uow.sales_invoices.get_by_id(invoice_id)
        if invoice is None:
            return
        if invoice.business_id != business_id:
            raise BusinessNotMemberException(
                "Invoice does not belong to the requested business",
                details={
                    "invoice_business_id": str(invoice.business_id),
                    "requested_business_id": str(business_id),
                },
            )
