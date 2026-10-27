"""Accounting inspection API router."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.common.exceptions import TaxPilotException
from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.accounting.api.dependencies import (
    get_accounting_unit_of_work,
    get_trial_balance_service,
)
from app.modules.accounting.schemas.inspection import (
    AccountDetailResponse,
    AccountResponse,
    GeneralLedgerEntryResponse,
    TrialBalanceAccountResponse,
    TrialBalanceResponse,
)
from app.modules.accounting.trial_balance.exceptions import (
    TrialBalanceFutureDateException,
)
from app.modules.accounting.trial_balance.services import TrialBalanceService
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.identity.dependencies import CurrentUser

CREDIT_NORMAL_CATEGORIES = {"liability", "equity", "revenue"}


class AccountNotFoundException(TaxPilotException):
    """Raised when an account cannot be found."""

    status_code: int = status.HTTP_404_NOT_FOUND
    error_code: str = "accounting.account_not_found"

    def __init__(
        self,
        message: str = "Account not found",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


class InvalidDateRangeException(TaxPilotException):
    """Raised when date_from is later than date_to."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "accounting.invalid_date_range"

    def __init__(
        self,
        message: str = "date_from cannot be later than date_to",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


router = APIRouter(prefix="/accounting", tags=["Accounting Inspection"])

AccountingUoWDependency = Annotated[
    Any,
    Depends(get_accounting_unit_of_work),
]

TrialBalanceServiceDependency = Annotated[
    TrialBalanceService,
    Depends(get_trial_balance_service),
]


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


def _format_source_document_url(
    source_entity: str | None,
    source_entity_id: uuid.UUID | None,
) -> str | None:
    """Generate the frontend route corresponding to a ledger line's source document."""
    if not source_entity or not source_entity_id:
        return None
    if source_entity == "sales_invoice":
        return f"/sales/invoices/{source_entity_id}"
    if source_entity in ("purchase_invoice", "supplier_payment"):
        return f"/purchases/invoices/{source_entity_id}"
    if source_entity in ("expense", "expense_payment"):
        return f"/expenses/{source_entity_id}"
    if source_entity == "payment":
        return f"/sales/invoices/{source_entity_id}"
    return None


@router.get(
    "/chart-of-accounts",
    response_model=SuccessResponse[list[AccountResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Chart of Accounts",
    description=(
        "Retrieves the configured Chart of Accounts for a business, "
        "with optional category filtering and search."
    ),
    responses={
        HTTPStatus.OK: {"description": "Chart of accounts retrieved successfully."},
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
async def list_chart_of_accounts(
    current_user: CurrentUser,
    uow: AccountingUoWDependency,
    business_id: Annotated[
        uuid.UUID,
        Query(description="Target tenant business identifier"),
    ],
    category: Annotated[
        str | None,
        Query(description="Filter by top-level category"),
    ] = None,
    is_active: Annotated[
        bool | None,
        Query(description="Filter by active status"),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Case-insensitive substring match on code or name"),
    ] = None,
) -> SuccessResponse[list[AccountResponse]]:
    """Return configured accounts and current balance metrics for a business."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        accounts = await uow.chart_of_accounts.list_accounts(
            business_id=business_id,
            category=category,
            is_active=is_active,
            search=search,
        )
        balances = await uow.account_balances.list_business_balances(business_id)
        balances_by_account = {b.account_id: b for b in balances}

        data: list[AccountResponse] = []
        for account in accounts:
            b = balances_by_account.get(account.id)
            current_debit = b.current_debit if b else Decimal("0.00")
            current_credit = b.current_credit if b else Decimal("0.00")
            current_balance = b.current_balance if b else Decimal("0.00")
            account_type = account.account_type
            category_name = (
                account_type.category.name
                if account_type and account_type.category
                else "Asset"
            )
            normal_bal = (
                "credit"
                if category_name.lower() in CREDIT_NORMAL_CATEGORIES
                else "debit"
            )

            data.append(
                AccountResponse(
                    id=account.id,
                    account_code=account.account_code,
                    account_name=account.account_name,
                    category_name=category_name,
                    account_type_name=account_type.name if account_type else "",
                    normal_balance=normal_bal,
                    current_debit=current_debit,
                    current_credit=current_credit,
                    current_balance=current_balance,
                    is_system=account.is_system,
                    is_active=account.is_active,
                    parent_account_id=account.parent_account_id,
                    description=account.description,
                )
            )

        return SuccessResponse(
            success=True,
            message="Chart of accounts retrieved successfully",
            data=data,
        )


@router.get(
    "/chart-of-accounts/{account_id}",
    response_model=SuccessResponse[AccountDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Account Detail",
    description=(
        "Retrieves detailed configuration and current balance metrics for "
        "a specific chart account."
    ),
    responses={
        HTTPStatus.OK: {"description": "Account detail retrieved successfully."},
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is required.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User is not a business member.",
        },
        HTTPStatus.NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Account not found.",
        },
    },
)
async def get_account_detail(
    account_id: uuid.UUID,
    current_user: CurrentUser,
    uow: AccountingUoWDependency,
    business_id: Annotated[
        uuid.UUID,
        Query(description="Target tenant business identifier"),
    ],
) -> SuccessResponse[AccountDetailResponse]:
    """Return detailed metrics for one chart account."""
    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        account = await uow.chart_of_accounts.get_by_id(
            business_id=business_id,
            account_id=account_id,
        )
        if account is None:
            raise AccountNotFoundException(
                "Account not found",
                details={
                    "business_id": str(business_id),
                    "account_id": str(account_id),
                },
            )

        b = await uow.account_balances.get_by_account(account.id)
        current_debit = b.current_debit if b else Decimal("0.00")
        current_credit = b.current_credit if b else Decimal("0.00")
        current_balance = b.current_balance if b else Decimal("0.00")
        account_type = account.account_type
        category_name = (
            account_type.category.name
            if account_type and account_type.category
            else "Asset"
        )
        normal_bal = (
            "credit"
            if category_name.lower() in CREDIT_NORMAL_CATEGORIES
            else "debit"
        )

        return SuccessResponse(
            success=True,
            message="Account detail retrieved successfully",
            data=AccountDetailResponse(
                id=account.id,
                account_code=account.account_code,
                account_name=account.account_name,
                category_name=category_name,
                account_type_name=account_type.name if account_type else "",
                normal_balance=normal_bal,
                current_debit=current_debit,
                current_credit=current_credit,
                current_balance=current_balance,
                is_system=account.is_system,
                is_active=account.is_active,
                parent_account_id=account.parent_account_id,
                description=account.description,
            ),
        )


@router.get(
    "/general-ledger",
    response_model=PaginatedApiResponse[GeneralLedgerEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="Inspect General Ledger",
    description=(
        "Retrieves paginated, chronological General Ledger entries with "
        "multi-criteria filtering, deterministic ordering, and source traceability."
    ),
    responses={
        HTTPStatus.OK: {
            "description": "General ledger entries retrieved successfully."
        },
        HTTPStatus.BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid query parameters.",
        },
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
async def list_general_ledger_entries(
    current_user: CurrentUser,
    uow: AccountingUoWDependency,
    business_id: Annotated[
        uuid.UUID,
        Query(description="Tenant business identifier"),
    ],
    account_id: Annotated[
        uuid.UUID | None,
        Query(description="Filter by specific account UUID"),
    ] = None,
    account_code: Annotated[
        str | None,
        Query(description="Filter by account code"),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(description="Start transaction date (YYYY-MM-DD)"),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="End transaction date (YYYY-MM-DD)"),
    ] = None,
    source_module: Annotated[
        str | None,
        Query(description="Filter by source: sales, purchases, expenses"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Pagination page number")] = 1,
    size: Annotated[
        int,
        Query(ge=1, le=100, description="Pagination page size"),
    ] = 20,
) -> PaginatedApiResponse[GeneralLedgerEntryResponse]:
    """Return chronological General Ledger entries with running balance semantics."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidDateRangeException(
            "date_from cannot be later than date_to",
            details={"date_from": str(date_from), "date_to": str(date_to)},
        )

    pagination = PaginationParams(page=page, size=size)

    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        gl_page = await uow.ledgers.list_entries(
            business_id=business_id,
            account_id=account_id,
            account_code=account_code,
            date_from=date_from,
            date_to=date_to,
            source_module=source_module,
            pagination=pagination,
        )

        data = [
            GeneralLedgerEntryResponse(
                id=entry.id,
                transaction_date=entry.transaction_date,
                posting_date=entry.posting_date,
                journal_entry_id=entry.journal_entry_id,
                journal_number=(
                    entry.journal_entry.journal_number
                    if entry.journal_entry
                    else ""
                ),
                journal_reference=(
                    entry.journal_entry.reference
                    if entry.journal_entry
                    else None
                ),
                account_id=entry.account_id,
                account_code=entry.account.account_code if entry.account else "",
                account_name=entry.account.account_name if entry.account else "",
                debit=entry.debit,
                credit=entry.credit,
                running_balance=entry.running_balance,
                description=entry.description,
                source_module=entry.source_module,
                source_entity=entry.source_entity,
                source_entity_id=entry.source_entity_id,
                source_document_url=_format_source_document_url(
                    entry.source_entity, entry.source_entity_id
                ),
            )
            for entry in gl_page.items
        ]

        return PaginatedApiResponse(
            success=True,
            message="General ledger entries retrieved successfully",
            data=data,
            meta=gl_page.meta,
        )


@router.get(
    "/trial-balance",
    response_model=SuccessResponse[TrialBalanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate Trial Balance",
    description=(
        "Computes a deterministic Trial Balance verifying mathematical equality "
        "between total debits and total credits as of a specified date."
    ),
    responses={
        HTTPStatus.OK: {"description": "Trial balance generated successfully."},
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
async def get_trial_balance(
    current_user: CurrentUser,
    uow: AccountingUoWDependency,
    trial_balance_service: TrialBalanceServiceDependency,
    business_id: Annotated[
        uuid.UUID,
        Query(description="Tenant business identifier"),
    ],
    as_of_date: Annotated[
        date | None,
        Query(description="Evaluation cutoff date (YYYY-MM-DD)"),
    ] = None,
    include_zero_balances: Annotated[
        bool,
        Query(description="Include accounts with zero net balance"),
    ] = False,
) -> SuccessResponse[TrialBalanceResponse]:
    if as_of_date is not None and as_of_date > datetime.now(tz=UTC).date():
        raise TrialBalanceFutureDateException(
            message=(
                f"Trial balance cannot be calculated for future date "
                f"{as_of_date.isoformat()}"
            ),
            details={"as_of_date": as_of_date.isoformat()},
        )

    async with uow:
        await _ensure_business_member(uow, business_id, current_user.id)
        tb = await trial_balance_service.generate(
            business_id=business_id,
            as_of_date=as_of_date,
            include_zero_balances=include_zero_balances,
            uow=uow,
        )

    data = TrialBalanceResponse(
        business_id=tb.business_id,
        generated_at=tb.generated_at,
        as_of_date=tb.as_of_date or datetime.now(tz=UTC).date(),
        total_debit=tb.total_debit,
        total_credit=tb.total_credit,
        discrepancy=tb.discrepancy,
        is_balanced=tb.is_balanced,
        historical_mode=tb.historical_mode,
        opening_balances_present=tb.opening_balances_present,
        fiscal_period_closed=tb.fiscal_period_closed,
        reporting_limitations=tb.reporting_limitations,
        accounts=[
            TrialBalanceAccountResponse(
                account_id=a.account_id,
                account_code=a.account_code,
                account_name=a.account_name,
                account_category=a.account_category,
                account_type=a.account_type,
                normal_balance=a.normal_balance,
                debit=a.debit,
                credit=a.credit,
                balance=a.balance,
            )
            for a in tb.accounts
        ],
    )

    return SuccessResponse(
        success=True,
        message="Trial balance generated successfully",
        data=data,
    )
