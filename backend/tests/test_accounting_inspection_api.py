"""Tests for Accounting Inspection API router."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Self

from fastapi.testclient import TestClient

from app.common.pagination import Page, PaginationParams
from app.core.model_registry import import_all_models
from app.main import create_app
from app.modules.accounting.api.dependencies import (
    get_accounting_unit_of_work,
    get_trial_balance_service,
)
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
)
from app.modules.accounting.journal.models import JournalEntry
from app.modules.accounting.ledger.models import GeneralLedgerEntry
from app.modules.accounting.trial_balance.models import (
    TrialBalance,
    TrialBalanceAccount,
)
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

import_all_models()

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404


def build_user() -> IdentityUser:
    """Build an authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )


def build_account(
    *,
    business_id: uuid.UUID,
    code: str,
    name: str,
    category_name: str,
    type_name: str,
    is_active: bool = True,
) -> Account:
    """Build an account with category and type."""
    category = AccountCategory(id=uuid.uuid4(), name=category_name)
    account_type = AccountType(
        id=uuid.uuid4(),
        category_id=category.id,
        name=type_name,
        category=category,
    )
    return Account(
        id=uuid.uuid4(),
        business_id=business_id,
        account_code=code,
        account_name=name,
        account_type_id=account_type.id,
        account_type=account_type,
        is_active=is_active,
        is_system=True,
    )


def build_ledger_entry(
    *,
    business_id: uuid.UUID,
    account: Account,
    journal_number: str,
    trans_date: date,
    debit: Decimal,
    credit: Decimal,
    running_balance: Decimal | None = None,
    source_module: str = "sales",
    source_entity: str = "sales_invoice",
    source_entity_id: uuid.UUID | None = None,
) -> GeneralLedgerEntry:
    """Build a mock general ledger entry."""
    entry_id = uuid.uuid4()
    journal = JournalEntry(
        id=uuid.uuid4(),
        business_id=business_id,
        journal_number=journal_number,
        transaction_date=trans_date,
        reference="REF-001",
    )
    return GeneralLedgerEntry(
        id=entry_id,
        business_id=business_id,
        journal_entry_id=journal.id,
        journal_line_id=uuid.uuid4(),
        account_id=account.id,
        transaction_date=trans_date,
        posting_date=trans_date,
        debit=debit,
        credit=credit,
        running_balance=running_balance,
        description=f"Entry for {journal_number}",
        source_module=source_module,
        source_entity=source_entity,
        source_entity_id=source_entity_id or uuid.uuid4(),
        journal_entry=journal,
        account=account,
    )


class FakeMembershipRepository:
    def __init__(
        self,
        *,
        is_member: bool = True,
        allowed_business_ids: set[uuid.UUID] | None = None,
    ) -> None:
        self.member = is_member
        self.allowed_business_ids = allowed_business_ids

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        _ = user_id
        if not self.member:
            return False
        if self.allowed_business_ids is not None:
            return business_id in self.allowed_business_ids
        return True


class FakeChartRepository:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = accounts

    async def list_accounts(
        self,
        *,
        business_id: uuid.UUID,
        category: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Account]:
        result = [a for a in self.accounts if a.business_id == business_id]
        if is_active is not None:
            result = [a for a in result if a.is_active == is_active]
        if category:
            result = [
                a
                for a in result
                if a.account_type
                and a.account_type.category
                and a.account_type.category.name.lower() == category.lower()
            ]
        if search:
            result = [
                a
                for a in result
                if search.lower() in a.account_code.lower()
                or search.lower() in a.account_name.lower()
            ]
        return result

    async def get_by_id(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> Account | None:
        for a in self.accounts:
            if a.business_id == business_id and a.id == account_id:
                return a
        return None


class FakeAccountBalanceRepository:
    def __init__(self, balances: list[AccountBalance]) -> None:
        self.balances = balances

    async def list_business_balances(
        self,
        business_id: uuid.UUID,
    ) -> list[AccountBalance]:
        return [b for b in self.balances if b.business_id == business_id]

    async def get_by_account(self, account_id: uuid.UUID) -> AccountBalance | None:
        for b in self.balances:
            if b.account_id == account_id:
                return b
        return None


class FakeLedgerRepository:
    def __init__(self, entries: list[GeneralLedgerEntry]) -> None:
        self.entries = entries

    async def list_entries(
        self,
        business_id: uuid.UUID,
        *,
        account_id: uuid.UUID | None = None,
        account_code: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        source_module: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> Page[GeneralLedgerEntry]:
        items = [e for e in self.entries if e.business_id == business_id]
        if account_id:
            items = [e for e in items if e.account_id == account_id]
        if account_code:
            items = [
                e
                for e in items
                if e.account and e.account.account_code == account_code
            ]
        if date_from:
            items = [e for e in items if e.transaction_date >= date_from]
        if date_to:
            items = [e for e in items if e.transaction_date <= date_to]
        if source_module:
            items = [e for e in items if e.source_module == source_module]

        params = pagination or PaginationParams()
        total = len(items)

        # Running balance semantics: if single account, compute running balance;
        # otherwise None
        if (account_id or account_code) and items:
            running = Decimal("0.00")
            for item in items:
                running += (item.debit - item.credit)
                item.running_balance = running
        else:
            for item in items:
                item.running_balance = None

        paged_items = items[params.offset : params.offset + params.limit]
        return Page.create(items=paged_items, total=total, params=params)


class FakeAccountingUnitOfWork:
    def __init__(
        self,
        *,
        accounts: list[Account],
        balances: list[AccountBalance],
        entries: list[GeneralLedgerEntry],
        is_member: bool = True,
        allowed_business_ids: set[uuid.UUID] | None = None,
    ) -> None:
        self.chart_of_accounts = FakeChartRepository(accounts)
        self.account_balances = FakeAccountBalanceRepository(balances)
        self.ledgers = FakeLedgerRepository(entries)
        self.business_memberships = FakeMembershipRepository(
            is_member=is_member,
            allowed_business_ids=allowed_business_ids,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass


class FakeTrialBalanceService:
    def __init__(self, trial_balance: TrialBalance) -> None:
        self._tb = trial_balance

    async def generate(
        self,
        business_id: uuid.UUID,
        *,
        as_of_date: date | None = None,
        include_zero_balances: bool = False,
        uow: object | None = None,
    ) -> TrialBalance:
        _ = business_id
        _ = include_zero_balances
        _ = uow
        return self._tb.model_copy(
            update={"as_of_date": as_of_date or self._tb.as_of_date}
        )


def build_test_setup(
    *,
    authenticated: bool = True,
    is_member: bool = True,
    business_id: uuid.UUID | None = None,
    entries: list[GeneralLedgerEntry] | None = None,
) -> tuple[TestClient, uuid.UUID, Account, Account, GeneralLedgerEntry]:
    bid = business_id or uuid.uuid4()
    cash = build_account(
        business_id=bid,
        code="1000",
        name="Cash",
        category_name="Asset",
        type_name="Current Asset",
    )
    sales = build_account(
        business_id=bid,
        code="4000",
        name="Sales Revenue",
        category_name="Revenue",
        type_name="Operating Revenue",
    )
    balance_cash = AccountBalance(
        business_id=bid,
        account_id=cash.id,
        current_debit=Decimal("10000.00"),
        current_credit=Decimal("0.00"),
        current_balance=Decimal("10000.00"),
    )
    balance_sales = AccountBalance(
        business_id=bid,
        account_id=sales.id,
        current_debit=Decimal("0.00"),
        current_credit=Decimal("10000.00"),
        current_balance=Decimal("-10000.00"),
    )

    source_invoice_id = uuid.uuid4()
    gl_entry = build_ledger_entry(
        business_id=bid,
        account=cash,
        journal_number="SINV-001",
        trans_date=date(2026, 10, 15),
        debit=Decimal("10000.00"),
        credit=Decimal("0.00"),
        source_module="sales",
        source_entity="sales_invoice",
        source_entity_id=source_invoice_id,
    )

    tb_accounts = [
        TrialBalanceAccount(
            account_id=cash.id,
            account_code="1000",
            account_name="Cash",
            account_type="Current Asset",
            account_category="Asset",
            normal_balance="debit",
            debit=Decimal("10000.00"),
            credit=Decimal("0.00"),
            balance=Decimal("10000.00"),
        ),
        TrialBalanceAccount(
            account_id=sales.id,
            account_code="4000",
            account_name="Sales Revenue",
            account_type="Operating Revenue",
            account_category="Revenue",
            normal_balance="credit",
            debit=Decimal("0.00"),
            credit=Decimal("10000.00"),
            balance=Decimal("10000.00"),
        ),
    ]
    tb = TrialBalance(
        business_id=bid,
        generated_at=datetime.now(tz=UTC),
        as_of_date=date(2026, 10, 20),
        total_debit=Decimal("10000.00"),
        total_credit=Decimal("10000.00"),
        discrepancy=Decimal("0.00"),
        is_balanced=True,
        historical_mode="ledger_derived_cumulative",
        opening_balances_present=False,
        fiscal_period_closed=False,
        reporting_limitations=[
            (
                "Balances reflect cumulative ledger entries recorded in "
                "TaxPilot from inception to date."
            ),
            (
                "Pre-system opening balances are not recorded; transactions "
                "prior to system go-live are not reflected."
            ),
            (
                "Fiscal year-end closing entries are not present; revenue and "
                "expense accounts reflect inception-to-date cumulative activity."
            ),
        ],
        accounts=tb_accounts,
    )

    uow = FakeAccountingUnitOfWork(
        accounts=[cash, sales],
        balances=[balance_cash, balance_sales],
        entries=entries if entries is not None else [gl_entry],
        is_member=is_member,
        allowed_business_ids={bid},
    )
    tb_service = FakeTrialBalanceService(tb)

    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_accounting_unit_of_work] = lambda: uow
    app.dependency_overrides[get_trial_balance_service] = lambda: tb_service
    if authenticated:
        app.dependency_overrides[get_current_user] = build_user

    return TestClient(app), bid, cash, sales, gl_entry


def test_list_chart_of_accounts_success() -> None:
    """AC-AIS-01: List chart of accounts returns all accounts in 200 OK."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        response = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}"
        )

    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["success"] is True
    expected_accounts = 2
    assert len(body["data"]) == expected_accounts
    codes = [a["account_code"] for a in body["data"]]
    assert "1000" in codes
    assert "4000" in codes
    cash_row = next(a for a in body["data"] if a["account_code"] == "1000")
    assert cash_row["category_name"] == "Asset"
    assert cash_row["normal_balance"] == "debit"
    assert cash_row["current_debit"] == "10000.00"


def test_list_chart_of_accounts_category_filter() -> None:
    """AC-AIS-02: Chart of accounts filters accurately by category."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        response = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}&category=Asset"
        )

    assert response.status_code == HTTP_OK
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["account_code"] == "1000"
    assert body["data"][0]["category_name"] == "Asset"


def test_get_account_detail_success_and_not_found() -> None:
    """Account detail returns 200 for existing account and 404 for unknown account."""
    client, business_id, cash, _sales, _entry = build_test_setup()

    with client:
        ok_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts/{cash.id}?business_id={business_id}"
        )
        nf_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts/{uuid.uuid4()}?business_id={business_id}"
        )

    assert ok_resp.status_code == HTTP_OK
    assert ok_resp.json()["data"]["id"] == str(cash.id)
    assert nf_resp.status_code == HTTP_NOT_FOUND


def test_general_ledger_source_traceability() -> None:
    """AC-AIS-05: GL entry provides source module, entity, ID, and frontend URL."""
    client, business_id, _cash, _sales, gl_entry = build_test_setup()

    with client:
        response = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
        )

    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["source_module"] == "sales"
    assert item["source_entity"] == "sales_invoice"
    assert item["source_entity_id"] == str(gl_entry.source_entity_id)
    assert item["source_document_url"] == f"/sales/invoices/{gl_entry.source_entity_id}"


def test_general_ledger_running_balance_semantics() -> None:
    """AC-AIS-06: Running balance is numeric for single account, null for all."""
    client, business_id, cash, _sales, _entry = build_test_setup()

    with client:
        # Multi-account query
        multi_resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
        )
        # Single-account query
        single_resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            f"&account_id={cash.id}"
        )

    assert multi_resp.status_code == HTTP_OK
    assert multi_resp.json()["data"][0]["running_balance"] is None

    assert single_resp.status_code == HTTP_OK
    assert single_resp.json()["data"][0]["running_balance"] == "10000.00"


def test_general_ledger_invalid_date_range() -> None:
    """GL returns 400 Bad Request when date_from > date_to."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        response = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&date_from=2026-10-20&date_to=2026-10-01"
        )

    assert response.status_code == HTTP_BAD_REQUEST


def test_trial_balance_equilibrium_and_disclosure() -> None:
    """AC-AIS-07 & AC-AIS-11: Affirm equilibrium and disclosures."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        response = client.get(
            f"/api/v1/accounting/trial-balance?business_id={business_id}&as_of_date=2026-10-15"
        )

    assert response.status_code == HTTP_OK
    body = response.json()
    data = body["data"]
    assert data["is_balanced"] is True
    assert data["discrepancy"] == "0.00"
    assert data["total_debit"] == "10000.00"
    assert data["total_credit"] == "10000.00"
    assert data["historical_mode"] == "ledger_derived_cumulative"
    assert data["opening_balances_present"] is False
    assert data["fiscal_period_closed"] is False
    expected_limitations = 3
    expected_accounts = 2
    assert len(data["reporting_limitations"]) == expected_limitations
    assert len(data["accounts"]) == expected_accounts


def test_cross_tenant_access_rejection() -> None:
    """AC-AIS-08A: Non-member user gets 403 Forbidden with zero data leaked."""
    client, business_id, cash, _sales, _entry = build_test_setup(is_member=False)

    with client:
        coa_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}"
        )
        detail_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts/{cash.id}"
            f"?business_id={business_id}"
        )
        gl_resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
        )
        tb_resp = client.get(
            f"/api/v1/accounting/trial-balance?business_id={business_id}"
        )

    for resp in (coa_resp, detail_resp, gl_resp, tb_resp):
        assert resp.status_code == HTTP_FORBIDDEN
        assert resp.json()["data"]["code"] == "business.not_member"


def test_account_detail_cross_tenant_isolation() -> None:
    """Cross-tenant account query under active tenant returns 404."""
    client, business_id, _cash, _sales, _entry = build_test_setup(is_member=True)
    foreign_account_id = uuid.uuid4()

    with client:
        resp = client.get(
            f"/api/v1/accounting/chart-of-accounts/{foreign_account_id}"
            f"?business_id={business_id}"
        )

    assert resp.status_code == HTTP_NOT_FOUND
    assert resp.json()["data"]["code"] == "accounting.account_not_found"


def test_unauthenticated_access_rejection() -> None:
    """AC-AIS-08B: Unauthenticated requests get 401 across all endpoints."""
    client, business_id, cash, _sales, _entry = build_test_setup(authenticated=False)

    with client:
        coa_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}"
        )
        detail_resp = client.get(
            f"/api/v1/accounting/chart-of-accounts/{cash.id}"
            f"?business_id={business_id}"
        )
        gl_resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
        )
        tb_resp = client.get(
            f"/api/v1/accounting/trial-balance?business_id={business_id}"
        )

    for resp in (coa_resp, detail_resp, gl_resp, tb_resp):
        assert resp.status_code == HTTP_UNAUTHORIZED
        assert resp.json()["data"]["code"] == "authentication.required"


def test_non_existent_business_rejection() -> None:
    """Non-existent business returns 403 without disclosing existence."""
    client, _business_id, _cash, _sales, _entry = build_test_setup()
    non_existent = uuid.uuid4()

    with client:
        resp = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={non_existent}"
        )

    assert resp.status_code == HTTP_FORBIDDEN
    assert resp.json()["data"]["code"] == "business.not_member"


def test_trial_balance_future_date_rejected() -> None:
    """Trial balance request with a future as_of_date returns 400 Bad Request."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        resp = client.get(
            f"/api/v1/accounting/trial-balance?business_id={business_id}"
            "&as_of_date=2099-01-01"
        )

    assert resp.status_code == HTTP_BAD_REQUEST
    body = resp.json()
    assert body["success"] is False
    assert body["data"]["code"] == "accounting.trial_balance_future_date"
    assert "future date" in body["message"]


def test_list_chart_of_accounts_search_filter() -> None:
    """Chart of accounts filters by search substring on code or name."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        resp_code = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}"
            "&search=1000"
        )
        resp_name = client.get(
            f"/api/v1/accounting/chart-of-accounts?business_id={business_id}"
            "&search=Revenue"
        )

    assert resp_code.status_code == HTTP_OK
    assert len(resp_code.json()["data"]) == 1
    assert resp_code.json()["data"][0]["account_code"] == "1000"

    assert resp_name.status_code == HTTP_OK
    assert len(resp_name.json()["data"]) == 1
    assert resp_name.json()["data"][0]["account_code"] == "4000"


def test_general_ledger_bounded_pagination() -> None:
    """AC-AIS-03: General Ledger bounded pagination and max limit check."""
    client_base, business_id, cash, _sales, _base_entry = build_test_setup()
    entry1 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-001",
        trans_date=date(2026, 10, 1),
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
    )
    entry2 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-002",
        trans_date=date(2026, 10, 2),
        debit=Decimal("200.00"),
        credit=Decimal("0.00"),
    )
    entry3 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-003",
        trans_date=date(2026, 10, 3),
        debit=Decimal("300.00"),
        credit=Decimal("0.00"),
    )
    client, _bid, _c, _s, _e = build_test_setup(
        business_id=business_id,
        entries=[entry1, entry2, entry3],
    )

    with client:
        page1 = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&page=1&size=2"
        )
        page2 = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&page=2&size=2"
        )
        oversize = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&size=101"
        )

    assert page1.status_code == HTTP_OK
    meta1 = page1.json()["meta"]
    expected_page_size = 2
    expected_total = 3
    expected_pages = 2
    expected_page_2 = 2
    expected_page_1_items = 2
    assert meta1["page"] == 1
    assert meta1["size"] == expected_page_size
    assert meta1["total"] == expected_total
    assert meta1["pages"] == expected_pages
    assert len(page1.json()["data"]) == expected_page_1_items

    assert page2.status_code == HTTP_OK
    meta2 = page2.json()["meta"]
    assert meta2["page"] == expected_page_2
    assert len(page2.json()["data"]) == 1

    assert oversize.status_code == HTTP_BAD_REQUEST


def test_general_ledger_date_filtering() -> None:
    """AC-AIS-04: General Ledger filters accurately by inclusive date range."""
    client_base, business_id, cash, _sales, _base_entry = build_test_setup()
    e_oct1 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-001",
        trans_date=date(2026, 10, 1),
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
    )
    e_oct15 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-002",
        trans_date=date(2026, 10, 15),
        debit=Decimal("200.00"),
        credit=Decimal("0.00"),
    )
    e_oct25 = build_ledger_entry(
        business_id=business_id,
        account=cash,
        journal_number="SINV-003",
        trans_date=date(2026, 10, 25),
        debit=Decimal("300.00"),
        credit=Decimal("0.00"),
    )
    client, _bid, _c, _s, _e = build_test_setup(
        business_id=business_id,
        entries=[e_oct1, e_oct15, e_oct25],
    )

    with client:
        resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&date_from=2026-10-10&date_to=2026-10-20"
        )

    assert resp.status_code == HTTP_OK
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["journal_number"] == "SINV-002"
    assert data[0]["transaction_date"] == "2026-10-15"


def test_general_ledger_account_code_filter() -> None:
    """GL filters by account_code and computes running balance."""
    client, business_id, cash, _sales, _entry = build_test_setup()

    with client:
        resp = client.get(
            f"/api/v1/accounting/general-ledger?business_id={business_id}"
            "&account_code=1000"
        )

    assert resp.status_code == HTTP_OK
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["account_code"] == "1000"
    assert data[0]["running_balance"] == "10000.00"


def test_historical_as_of_trial_balance_api() -> None:
    """AC-AIS-09: As-of cutoff date parameter passes to trial balance API."""
    client, business_id, _cash, _sales, _entry = build_test_setup()

    with client:
        resp = client.get(
            f"/api/v1/accounting/trial-balance?business_id={business_id}"
            "&as_of_date=2026-10-15"
        )

    assert resp.status_code == HTTP_OK
    data = resp.json()["data"]
    assert data["as_of_date"] == "2026-10-15"
    assert data["is_balanced"] is True
