"""Sales API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.identity.dependencies import CurrentUser
from app.modules.sales.api.dependencies import (
    get_canonical_sales_invoice_service,
    get_sales_intelligence_service,
    get_sales_invoice_service,
    get_sales_unit_of_work,
)
from app.modules.sales.canonical_schemas import (
    CanonicalInvoiceDraftRequest,
    CanonicalInvoiceDraftUpdate,
    CanonicalInvoiceResponse,
)
from app.modules.sales.canonical_service import CanonicalSalesInvoiceService
from app.modules.sales.exceptions import (
    SalesCustomerNotFoundException,
    SalesDuplicateCustomerException,
    SalesInvoiceNotFoundException,
)
from app.modules.sales.intelligence import (
    InvoiceIntelligenceResponse,
    SalesIntelligenceService,
)
from app.modules.sales.models import Customer, SalesInvoice
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
    InvoiceCreateRequest,
    InvoiceResponse,
    InvoiceSummaryResponse,
    InvoiceUpdateRequest,
)
from app.modules.sales.services import SalesInvoiceService

router = APIRouter(prefix="/sales", tags=["Sales"])
SalesInvoiceServiceDependency = Annotated[
    SalesInvoiceService,
    Depends(get_sales_invoice_service),
]
SalesUnitOfWorkDependency = Annotated[
    Any,
    Depends(get_sales_unit_of_work),
]
CanonicalSalesServiceDependency = Annotated[
    CanonicalSalesInvoiceService, Depends(get_canonical_sales_invoice_service)
]
SalesIntelligenceServiceDependency = Annotated[
    SalesIntelligenceService, Depends(get_sales_intelligence_service)
]


@router.get(
    "/workflow/invoices",
    response_model=PaginatedApiResponse[InvoiceSummaryResponse],
)
async def list_canonical_invoices(
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedApiResponse[InvoiceSummaryResponse]:
    """List only invoices migrated to the canonical CatalogItem workflow."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        result = await uow.sales_invoices.list_canonical_business_invoices(
            business_id,
            PaginationParams(page=page, size=page_size),
        )
    return PaginatedApiResponse(
        success=True,
        message="Canonical invoices returned",
        data=[InvoiceSummaryResponse.model_validate(item) for item in result.items],
        meta=result.meta,
    )


@router.post(
    "/workflow/invoices",
    response_model=SuccessResponse[CanonicalInvoiceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_canonical_invoice(
    request: CanonicalInvoiceDraftRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: CanonicalSalesServiceDependency,
) -> SuccessResponse[CanonicalInvoiceResponse]:
    async with uow:
        await _ensure_business_member(uow, request.business_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Canonical invoice draft created",
        data=await service.create_draft(request),
    )


@router.get(
    "/workflow/invoices/{invoice_id}",
    response_model=SuccessResponse[CanonicalInvoiceResponse],
)
async def get_canonical_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: CanonicalSalesServiceDependency,
) -> SuccessResponse[CanonicalInvoiceResponse]:
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Canonical invoice returned",
        data=await service.get(invoice_id),
    )


@router.get(
    "/workflow/invoices/{invoice_id}/recommendations",
    response_model=SuccessResponse[InvoiceIntelligenceResponse],
)
async def get_invoice_recommendations(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: SalesIntelligenceServiceDependency,
) -> SuccessResponse[InvoiceIntelligenceResponse]:
    """Return advisory intelligence without modifying the invoice."""
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Invoice recommendations returned",
        data=await service.evaluate(invoice_id),
    )


@router.patch(
    "/workflow/invoices/{invoice_id}",
    response_model=SuccessResponse[CanonicalInvoiceResponse],
)
async def update_canonical_invoice(
    invoice_id: uuid.UUID,
    request: CanonicalInvoiceDraftUpdate,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: CanonicalSalesServiceDependency,
) -> SuccessResponse[CanonicalInvoiceResponse]:
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Canonical invoice draft updated",
        data=await service.update_draft(invoice_id, request),
    )


@router.post(
    "/workflow/invoices/{invoice_id}/issue",
    response_model=SuccessResponse[CanonicalInvoiceResponse],
)
async def issue_canonical_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: CanonicalSalesServiceDependency,
) -> SuccessResponse[CanonicalInvoiceResponse]:
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Canonical invoice issued",
        data=await service.issue(invoice_id),
    )


@router.post(
    "/workflow/invoices/{invoice_id}/cancel",
    response_model=SuccessResponse[CanonicalInvoiceResponse],
)
async def cancel_canonical_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    service: CanonicalSalesServiceDependency,
) -> SuccessResponse[CanonicalInvoiceResponse]:
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)
    return SuccessResponse(
        success=True,
        message="Canonical invoice cancelled",
        data=await service.cancel(invoice_id),
    )


@router.post(
    "/customers",
    response_model=SuccessResponse[CustomerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
    description="Creates a customer for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.CREATED: {"description": "Customer created successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User is not a business member.",
        },
        HTTPStatus.CONFLICT: {
            "model": ErrorResponse,
            "description": "Customer code or email already exists.",
        },
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "model": ErrorResponse,
            "description": "Request validation failed.",
        },
    },
)
async def create_customer(
    request: CustomerCreateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
) -> SuccessResponse[CustomerResponse]:
    """Create a customer."""
    async with uow:
        await _ensure_business_member(uow, request.business_id, current_user.id)
        if await uow.customers.exists_by_code(
            business_id=request.business_id,
            customer_code=request.customer_code,
        ):
            raise SalesDuplicateCustomerException(
                "Customer code already exists",
                details={"customer_code": request.customer_code},
            )
        if request.email and await uow.customers.exists_by_email(
            business_id=request.business_id,
            email=request.email,
        ):
            raise SalesDuplicateCustomerException(
                "Customer email already exists",
                details={"email": request.email},
            )
        customer = await uow.customers.create(request)
        await uow.commit()

    return SuccessResponse(
        success=True,
        message="Customer created successfully",
        data=CustomerResponse.model_validate(customer),
    )


@router.get(
    "/customers",
    response_model=PaginatedApiResponse[CustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="List customers",
    description="Lists customers for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Customers returned successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User is not a business member.",
        },
    },
)
async def list_customers(
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginatedApiResponse[CustomerResponse]:
    """List customers."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        customer_page = await uow.customers.list_business_customers(
            business_id,
            PaginationParams(page=page, size=page_size),
        )

    return PaginatedApiResponse(
        success=True,
        message="Customers returned successfully",
        data=[
            CustomerResponse.model_validate(customer)
            for customer in customer_page.items
        ],
        meta=customer_page.meta,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=SuccessResponse[CustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="Get customer",
    description=(
        "Returns a customer when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Customer returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_customer(
    customer_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
) -> SuccessResponse[CustomerResponse]:
    """Return a customer."""
    async with uow:
        customer = await _get_customer_for_user(uow, customer_id, current_user.id)

    return SuccessResponse(
        success=True,
        message="Customer returned successfully",
        data=CustomerResponse.model_validate(customer),
    )


@router.patch(
    "/customers/{customer_id}",
    response_model=SuccessResponse[CustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="Update customer",
    description=(
        "Updates a customer when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Customer updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_customer(
    customer_id: uuid.UUID,
    request: CustomerUpdateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
) -> SuccessResponse[CustomerResponse]:
    """Update a customer."""
    async with uow:
        customer = await _get_customer_for_user(uow, customer_id, current_user.id)
        if (
            request.customer_code
            and request.customer_code != customer.customer_code
            and await uow.customers.exists_by_code(
                business_id=customer.business_id,
                customer_code=request.customer_code,
            )
        ):
            raise SalesDuplicateCustomerException(
                "Customer code already exists",
                details={"customer_code": request.customer_code},
            )
        if (
            request.email
            and request.email != customer.email
            and await uow.customers.exists_by_email(
                business_id=customer.business_id,
                email=request.email,
            )
        ):
            raise SalesDuplicateCustomerException(
                "Customer email already exists",
                details={"email": request.email},
            )
        customer = await uow.customers.update(customer, request)
        await uow.commit()

    return SuccessResponse(
        success=True,
        message="Customer updated successfully",
        data=CustomerResponse.model_validate(customer),
    )


@router.post(
    "/invoices",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice",
    description="Creates a sales invoice for a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Invoice created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_invoice(
    request: InvoiceCreateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    invoice_service: SalesInvoiceServiceDependency,
) -> SuccessResponse[InvoiceResponse]:
    """Create an invoice."""
    async with uow:
        await _ensure_business_member(uow, request.business_id, current_user.id)

    invoice = await invoice_service.create_invoice(request)
    return SuccessResponse(
        success=True,
        message="Invoice created successfully",
        data=invoice,
    )


@router.get(
    "/invoices",
    response_model=PaginatedApiResponse[InvoiceSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List invoices",
    description="Lists invoices for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Invoices returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_invoices(
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginatedApiResponse[InvoiceSummaryResponse]:
    """List invoices."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        invoice_page = await uow.sales_invoices.list_business_invoices(
            business_id,
            PaginationParams(page=page, size=page_size),
        )

    return PaginatedApiResponse(
        success=True,
        message="Invoices returned successfully",
        data=[
            InvoiceSummaryResponse.model_validate(invoice)
            for invoice in invoice_page.items
        ],
        meta=invoice_page.meta,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get invoice",
    description=(
        "Returns an invoice when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Invoice returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
) -> SuccessResponse[InvoiceResponse]:
    """Return an invoice."""
    async with uow:
        invoice = await _get_invoice_for_user(uow, invoice_id, current_user.id)

    return SuccessResponse(
        success=True,
        message="Invoice returned successfully",
        data=InvoiceResponse.model_validate(invoice),
    )


@router.patch(
    "/invoices/{invoice_id}",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update invoice",
    description=(
        "Updates an invoice when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Invoice updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_invoice(
    invoice_id: uuid.UUID,
    request: InvoiceUpdateRequest,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    invoice_service: SalesInvoiceServiceDependency,
) -> SuccessResponse[InvoiceResponse]:
    """Update an invoice."""
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)

    invoice = await invoice_service.update_invoice(invoice_id, request)
    return SuccessResponse(
        success=True,
        message="Invoice updated successfully",
        data=invoice,
    )


@router.post(
    "/invoices/{invoice_id}/issue",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Issue invoice",
    description="Issues a draft invoice for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Invoice issued successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def issue_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    invoice_service: SalesInvoiceServiceDependency,
) -> SuccessResponse[InvoiceResponse]:
    """Issue an invoice."""
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)

    invoice = await invoice_service.issue_invoice(invoice_id)
    return SuccessResponse(
        success=True,
        message="Invoice issued successfully",
        data=invoice,
    )


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=SuccessResponse[InvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel invoice",
    description="Cancels an invoice for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Invoice cancelled successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    uow: SalesUnitOfWorkDependency,
    invoice_service: SalesInvoiceServiceDependency,
) -> SuccessResponse[InvoiceResponse]:
    """Cancel an invoice."""
    async with uow:
        await _get_invoice_for_user(uow, invoice_id, current_user.id)

    invoice = await invoice_service.cancel_invoice(invoice_id)
    return SuccessResponse(
        success=True,
        message="Invoice cancelled successfully",
        data=invoice,
    )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when the current user is not a member of the business."""
    await ensure_active_business_membership(
        uow,
        business_id=business_id,
        user_id=user_id,
        entered=True,
    )


async def _get_customer_for_user(
    uow: Any,
    customer_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Customer:
    """Return a customer after enforcing business membership."""
    customer = await uow.customers.get_by_id(customer_id)
    if customer is None:
        raise SalesCustomerNotFoundException(
            "Customer not found",
            details={"customer_id": str(customer_id)},
        )
    await _ensure_business_member(uow, customer.business_id, user_id)
    return cast(Customer, customer)


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
    await _ensure_business_member(uow, invoice.business_id, user_id)
    return cast(SalesInvoice, invoice)
