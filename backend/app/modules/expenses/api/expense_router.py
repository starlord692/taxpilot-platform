"""Expense API router."""

import uuid
from datetime import date
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.expenses.api.dependencies import (
    get_expense_service,
    get_expense_unit_of_work,
)
from app.modules.expenses.exceptions import ExpenseNotFoundException
from app.modules.expenses.models import Expense, ExpenseStatus
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.modules.expenses.services import ExpenseService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/expenses", tags=["Expenses"])
ExpenseServiceDependency = Annotated[ExpenseService, Depends(get_expense_service)]
ExpenseUnitOfWorkDependency = Annotated[Any, Depends(get_expense_unit_of_work)]


@router.post(
    "",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create expense",
    description="Creates an expense for a business member.",
    responses={
        HTTPStatus.CREATED: {"description": "Expense created successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_expense(
    request: ExpenseCreate,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[ExpenseResponse]:
    """Create an expense."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    expense = await expense_service.create_expense(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="Expense created successfully",
        data=expense,
    )


@router.get(
    "",
    response_model=PaginatedApiResponse[ExpenseListResponse],
    status_code=status.HTTP_200_OK,
    summary="List expenses",
    description="Lists expenses for a business the authenticated user belongs to.",
    responses={
        HTTPStatus.OK: {"description": "Expenses returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
    },
)
async def list_expenses(
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
    sort: Annotated[
        str | None,
        Query(description="Sort field, e.g. expense_date, -expense_date."),
    ] = None,
    vendor_id: Annotated[
        uuid.UUID | None,
        Query(description="Optional vendor UUID filter."),
    ] = None,
    status_filter: Annotated[
        ExpenseStatus | None,
        Query(alias="status", description="Optional expense status filter."),
    ] = None,
    expense_date_from: Annotated[
        date | None,
        Query(description="Optional inclusive expense date lower bound."),
    ] = None,
    expense_date_to: Annotated[
        date | None,
        Query(description="Optional inclusive expense date upper bound."),
    ] = None,
) -> PaginatedApiResponse[ExpenseListResponse]:
    """List expenses."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)

    expense_page = await expense_service.list_expenses(
        business_id,
        PaginationParams(page=page, size=page_size),
        sort=sort,
        vendor_id=vendor_id,
        status=status_filter,
        expense_date_from=expense_date_from,
        expense_date_to=expense_date_to,
    )
    return PaginatedApiResponse(
        success=True,
        message="Expenses returned successfully",
        data=[
            ExpenseListResponse.model_validate(expense)
            for expense in expense_page.items
        ],
        meta=expense_page.meta,
    )


@router.get(
    "/{expense_id}",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Get expense",
    description=(
        "Returns an expense when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Expense returned successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_expense(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
) -> SuccessResponse[ExpenseResponse]:
    """Return an expense."""
    async with uow:
        await _get_expense_for_user(uow, expense_id, current_user.id)

    expense = await expense_service.get_expense(expense_id)
    return SuccessResponse(
        success=True,
        message="Expense returned successfully",
        data=expense,
    )


@router.patch(
    "/{expense_id}",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Update expense",
    description=(
        "Updates an expense when the authenticated user belongs to its business."
    ),
    responses={
        HTTPStatus.OK: {"description": "Expense updated successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def update_expense(
    expense_id: uuid.UUID,
    request: ExpenseUpdate,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
) -> SuccessResponse[ExpenseResponse]:
    """Update an expense."""
    async with uow:
        await _get_expense_for_user(uow, expense_id, current_user.id)

    expense = await expense_service.update_expense(expense_id, request)
    return SuccessResponse(
        success=True,
        message="Expense updated successfully",
        data=expense,
    )


@router.post(
    "/{expense_id}/approve",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve expense",
    description="Approves a draft expense for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Expense approved successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def approve_expense(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
) -> SuccessResponse[ExpenseResponse]:
    """Approve an expense."""
    async with uow:
        await _get_expense_for_user(uow, expense_id, current_user.id)

    expense = await expense_service.approve_expense(expense_id)
    return SuccessResponse(
        success=True,
        message="Expense approved successfully",
        data=expense,
    )


@router.post(
    "/{expense_id}/pay",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Mark expense paid",
    description="Marks an approved expense as paid for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Expense marked paid successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def mark_expense_paid(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
) -> SuccessResponse[ExpenseResponse]:
    """Mark an expense paid."""
    async with uow:
        await _get_expense_for_user(uow, expense_id, current_user.id)

    expense = await expense_service.mark_paid(expense_id)
    return SuccessResponse(
        success=True,
        message="Expense marked paid successfully",
        data=expense,
    )


@router.post(
    "/{expense_id}/cancel",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel expense",
    description="Cancels an expense for a business member.",
    responses={
        HTTPStatus.OK: {"description": "Expense cancelled successfully."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def cancel_expense(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    uow: ExpenseUnitOfWorkDependency,
    expense_service: ExpenseServiceDependency,
) -> SuccessResponse[ExpenseResponse]:
    """Cancel an expense."""
    async with uow:
        await _get_expense_for_user(uow, expense_id, current_user.id)

    expense = await expense_service.cancel_expense(expense_id)
    return SuccessResponse(
        success=True,
        message="Expense cancelled successfully",
        data=expense,
    )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when the current user is not a member of the business."""
    if not await uow.business_memberships.is_member(
        business_id=business_id,
        user_id=user_id,
    ):
        raise BusinessNotMemberException(
            "User is not a member of the business",
            details={"business_id": str(business_id), "user_id": str(user_id)},
        )


async def _get_expense_for_user(
    uow: Any,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Expense:
    """Return an expense after enforcing business membership."""
    expense = await uow.expenses.get_by_id(expense_id)
    if expense is None:
        raise ExpenseNotFoundException(
            "Expense not found",
            details={"expense_id": str(expense_id)},
        )
    await _ensure_business_member(uow, expense.business_id, user_id)
    return cast(Expense, expense)
