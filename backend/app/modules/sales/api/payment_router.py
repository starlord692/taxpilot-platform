"""Sales payment API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Response, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.identity.dependencies import CurrentUser
from app.modules.sales.api.dependencies import (
    get_payment_service,
    get_sales_unit_of_work,
)
from app.modules.sales.exceptions import (
    SalesInvoiceNotFoundException,
    SalesPaymentNotFoundException,
)
from app.modules.sales.models import Payment, SalesInvoice
from app.modules.sales.schemas import PaymentCreateRequest, PaymentResponse
from app.modules.sales.services import PaymentService

router = APIRouter(prefix="/sales/payments", tags=["Sales Payments"])
PaymentServiceDependency = Annotated[PaymentService, Depends(get_payment_service)]
SalesUnitOfWorkDependency = Annotated[Any, Depends(get_sales_unit_of_work)]


@router.post(
    "",
    response_model=SuccessResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record payment",
    description="Records a payment for an invoice owned by a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Payment recorded successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def record_payment(
    request: PaymentCreateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    payment_service: PaymentServiceDependency,
) -> SuccessResponse[PaymentResponse]:
    """Record a payment."""
    async with uow:
        await _get_invoice_for_user(uow, request.invoice_id, current_user.id)

    payment = await payment_service.record_payment(request)
    return SuccessResponse(
        success=True,
        message="Payment recorded successfully",
        data=payment,
    )


@router.get(
    "/{payment_id}",
    response_model=SuccessResponse[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get payment",
    description=(
        "Returns a payment when the authenticated user belongs to the invoice business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Payment returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_payment(
    payment_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
) -> SuccessResponse[PaymentResponse]:
    """Return a payment."""
    async with uow:
        payment = await _get_payment_for_user(uow, payment_id, current_user.id)

    return SuccessResponse(
        success=True,
        message="Payment returned successfully",
        data=PaymentResponse.model_validate(payment),
    )


@router.patch(
    "/{payment_id}",
    response_model=SuccessResponse[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update payment",
    description="Updates a payment for an invoice owned by a business member.",
    responses={
        HTTPStatus.OK: {"description": "Payment updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_payment(
    payment_id: uuid.UUID,
    request: PaymentCreateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    payment_service: PaymentServiceDependency,
) -> SuccessResponse[PaymentResponse]:
    """Update a payment."""
    async with uow:
        await _get_payment_for_user(uow, payment_id, current_user.id)
        await _get_invoice_for_user(uow, request.invoice_id, current_user.id)

    payment = await payment_service.update_payment(payment_id, request)
    return SuccessResponse(
        success=True,
        message="Payment updated successfully",
        data=payment,
    )


@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete payment",
    description="Deletes a payment for an invoice owned by a business member.",
    responses={
        HTTPStatus.NO_CONTENT: {"description": "Payment deleted successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def delete_payment(
    payment_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    payment_service: PaymentServiceDependency,
) -> Response:
    """Delete a payment."""
    async with uow:
        await _get_payment_for_user(uow, payment_id, current_user.id)

    await payment_service.delete_payment(payment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _get_payment_for_user(
    uow: Any,
    payment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Payment:
    """Return a payment after enforcing invoice business membership."""
    payment = await uow.payments.get_by_id(payment_id)
    if payment is None:
        raise SalesPaymentNotFoundException(
            "Payment not found",
            details={"payment_id": str(payment_id)},
        )
    await _get_invoice_for_user(uow, payment.invoice_id, user_id)
    return cast(Payment, payment)


async def _get_invoice_for_user(
    uow: Any,
    invoice_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SalesInvoice:
    """Return an invoice after enforcing business membership."""
    invoice = await uow.sales_invoices.get_by_id(invoice_id)
    if invoice is None:
        raise SalesInvoiceNotFoundException(
            "Invoice not found",
            details={"invoice_id": str(invoice_id)},
        )
    await ensure_active_business_membership(
        uow,
        business_id=invoice.business_id,
        user_id=user_id,
        entered=True,
    )
    return cast(SalesInvoice, invoice)
