"""Tests for the Accounting Kernel integration."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self, cast

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.accounting.balances.events import AccountBalanceUpdatedEvent
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import Account
from app.modules.accounting.journal.events import JournalPostedEvent
from app.modules.accounting.journal.models import JournalEntry, JournalStatus
from app.modules.accounting.kernel import (
    AccountingExpensePaymentPostedEvent,
    AccountingExpensePostedEvent,
    AccountingInvoicePostedEvent,
    AccountingKernelService,
    AccountingPaymentPostedEvent,
    AccountingPurchasePaymentPostedEvent,
    AccountingPurchasePostedEvent,
)
from app.modules.accounting.kernel.accounting_kernel import AccountingKernelUnitOfWork
from app.modules.accounting.ledger.events import LedgerPostedEvent
from app.modules.accounting.ledger.exceptions import LedgerPostingFailedException
from app.modules.accounting.ledger.models import GeneralLedgerEntry
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus
from app.modules.sales.models import InvoiceStatus, Payment, PaymentMethod, SalesInvoice

pytestmark = pytest.mark.asyncio
INVOICE_POSTING_ENTRY_COUNT = 3
PAYMENT_POSTING_ENTRY_COUNT = 2
EXPENSE_POSTING_ENTRY_COUNT = 3
EXPENSE_PAYMENT_POSTING_ENTRY_COUNT = 2
PURCHASE_POSTING_ENTRY_COUNT = 3
PURCHASE_PAYMENT_POSTING_ENTRY_COUNT = 2


class FakeInvoiceRepository:
    """Fake invoice repository for accounting kernel tests."""

    def __init__(self, invoice: SalesInvoice | None) -> None:
        """Initialize with an invoice."""
        self.invoice = invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return configured invoice by id."""
        if self.invoice is None or self.invoice.id != invoice_id:
            return None
        return self.invoice


class FakePaymentRepository:
    """Fake payment repository for accounting kernel tests."""

    def __init__(self, payment: Payment | None) -> None:
        """Initialize with a payment."""
        self.payment = payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return configured payment by id."""
        if self.payment is None or self.payment.id != payment_id:
            return None
        return self.payment


class FakeExpenseRepository:
    """Fake expense repository for accounting kernel tests."""

    def __init__(self, expense: Expense | None) -> None:
        """Initialize with an expense."""
        self.expense = expense

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return configured expense by id."""
        if self.expense is None or self.expense.id != expense_id:
            return None
        return self.expense


class FakePurchaseRepository:
    """Fake purchase repository for accounting kernel tests."""

    def __init__(self, purchase: PurchaseInvoice | None) -> None:
        """Initialize with a purchase invoice."""
        self.purchase = purchase

    async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
        """Return configured purchase invoice by id."""
        if self.purchase is None or self.purchase.id != purchase_id:
            return None
        return self.purchase


class FakeChartRepository:
    """Fake chart repository for accounting kernel tests."""

    def __init__(self, accounts: dict[str, Account]) -> None:
        """Initialize with account code mapping."""
        self.accounts = accounts
        self.requested_codes: list[str] = []

    async def get_account_by_code(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
    ) -> Account | None:
        """Return a configured business account."""
        self.requested_codes.append(account_code)
        account = self.accounts.get(account_code)
        if account is None or account.business_id != business_id:
            return None
        return account


class FakeJournalRepository:
    """Fake journal repository for accounting kernel tests."""

    def __init__(self) -> None:
        """Initialize captured journals."""
        self.journals: list[JournalEntry] = []

    async def add(self, entity: JournalEntry) -> JournalEntry:
        """Persist a journal in memory."""
        entity.id = entity.id or uuid.uuid4()
        for line in entity.lines:
            line.id = line.id or uuid.uuid4()
            line.journal_entry_id = entity.id
        self.journals.append(entity)
        return entity

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        """Mark a journal posted."""
        journal.status = JournalStatus.POSTED
        journal.posting_date = posting_date
        return journal


class FakeLedgerRepository:
    """Fake ledger repository for accounting kernel tests."""

    def __init__(self, *, fail_create: bool = False) -> None:
        """Initialize fake ledger behavior."""
        self.entries: list[GeneralLedgerEntry] = []
        self.fail_create = fail_create

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        """Persist ledger entries in memory."""
        if self.fail_create:
            raise RuntimeError("ledger failed")
        for entry in entries:
            entry.id = entry.id or uuid.uuid4()
        self.entries.extend(entries)
        return entries

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        """Return whether ledger entries exist for a journal."""
        return any(entry.journal_entry_id == journal_id for entry in self.entries)


class FakeBalanceRepository:
    """Fake balance repository for accounting kernel tests."""

    def __init__(self) -> None:
        """Initialize fake balances."""
        self.balances: dict[uuid.UUID, AccountBalance] = {}

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        """Create or return a fake balance."""
        if account_id not in self.balances:
            self.balances[account_id] = AccountBalance(
                id=uuid.uuid4(),
                business_id=business_id,
                account_id=account_id,
                current_debit=Decimal("0.00"),
                current_credit=Decimal("0.00"),
                current_balance=Decimal("0.00"),
            )
        return self.balances[account_id]

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        """Apply fake balance deltas."""
        _ = last_posted_at
        balance.current_debit += debit_delta
        balance.current_credit += credit_delta
        balance.current_balance = balance.current_debit - balance.current_credit
        return balance


class FakeAccountingUnitOfWork:
    """Fake Unit of Work for accounting kernel tests."""

    def __init__(
        self,
        *,
        invoice: SalesInvoice | None = None,
        payment: Payment | None = None,
        expense: Expense | None = None,
        purchase: PurchaseInvoice | None = None,
        fail_ledger: bool = False,
    ) -> None:
        """Initialize fake repositories."""
        self.sales_invoices = FakeInvoiceRepository(invoice)
        self.payments = FakePaymentRepository(payment)
        self.expenses = FakeExpenseRepository(expense)
        self.purchase_invoices = FakePurchaseRepository(purchase)
        business_id = self._get_business_id(invoice, expense, purchase)
        self.chart_of_accounts = FakeChartRepository(
            build_accounts(business_id)
        )
        self.journals = FakeJournalRepository()
        self.ledgers = FakeLedgerRepository(fail_create=fail_ledger)
        self.account_balances = FakeBalanceRepository()
        self.committed = False
        self.rolled_back = False

    def _get_business_id(
        self,
        invoice: SalesInvoice | None,
        expense: Expense | None,
        purchase: PurchaseInvoice | None,
    ) -> uuid.UUID:
        """Return the business id used for fake chart accounts."""
        if invoice is not None:
            return invoice.business_id
        if expense is not None:
            return expense.business_id
        if purchase is not None:
            return purchase.business_id
        return uuid.uuid4()

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback uncommitted fake transactions."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Record and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


def build_accounts(business_id: uuid.UUID) -> dict[str, Account]:
    """Build required accounting accounts."""
    return {
        code: Account(
            id=uuid.uuid4(),
            business_id=business_id,
            account_code=code,
            account_name=name,
            account_type_id=uuid.uuid4(),
            is_system=True,
            is_active=True,
        )
        for code, name in {
            "1000": "Cash",
            "1010": "Bank",
            "1020": "Accounts Receivable",
            "1050": "Input GST",
            "2000": "Accounts Payable",
            "2010": "GST Payable",
            "4000": "Sales",
            "5000": "Cost of Goods Sold",
            "5600": "Internet",
            "5900": "Miscellaneous",
        }.items()
    }


def build_invoice() -> SalesInvoice:
    """Build an issued invoice."""
    return SalesInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=InvoiceStatus.ISSUED,
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )


def build_payment(invoice_id: uuid.UUID) -> Payment:
    """Build a customer payment."""
    return Payment(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
        reference_number="UPI-123",
    )


def build_expense(
    *,
    status: ExpenseStatus = ExpenseStatus.APPROVED,
) -> Expense:
    """Build an expense."""
    return Expense(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        status=status,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )


def build_purchase(
    *,
    status: PurchaseStatus = PurchaseStatus.APPROVED,
) -> PurchaseInvoice:
    """Build a purchase invoice."""
    return PurchaseInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        status=status,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )


def build_service(
    uow: FakeAccountingUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> AccountingKernelService:
    """Build the accounting kernel service."""
    return AccountingKernelService(
        unit_of_work_factory=lambda: cast(AccountingKernelUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )


async def test_invoice_creates_journal_ledger_and_balances() -> None:
    """Sales invoice posting creates journal, ledger entries, and balances."""
    invoice = build_invoice()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(invoice=invoice)
    service = build_service(uow, dispatcher)

    journal = await service.record_sales_invoice(invoice.id)

    assert journal.status == JournalStatus.POSTED
    assert journal.description == "Sales Invoice INV-0001"
    assert len(journal.lines) == INVOICE_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == INVOICE_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == INVOICE_POSTING_ENTRY_COUNT
    assert uow.committed is True


async def test_invoice_posting_publishes_events() -> None:
    """Sales invoice posting publishes accounting pipeline events."""
    invoice = build_invoice()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(invoice=invoice)
    service = build_service(uow, dispatcher)

    await service.record_sales_invoice(invoice.id)

    assert any(isinstance(event, JournalPostedEvent) for event in dispatcher.events)
    assert any(isinstance(event, LedgerPostedEvent) for event in dispatcher.events)
    assert any(
        isinstance(event, AccountBalanceUpdatedEvent)
        for event in dispatcher.events
    )
    assert any(
        isinstance(event, AccountingInvoicePostedEvent)
        for event in dispatcher.events
    )


async def test_payment_creates_journal_and_updates_balances() -> None:
    """Customer payment posting creates ledger entries and updates balances."""
    invoice = build_invoice()
    payment = build_payment(invoice.id)
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(invoice=invoice, payment=payment)
    service = build_service(uow, dispatcher)

    journal = await service.record_customer_payment(payment.id)

    assert journal.status == JournalStatus.POSTED
    assert len(journal.lines) == PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == PAYMENT_POSTING_ENTRY_COUNT
    assert any(
        isinstance(event, AccountingPaymentPostedEvent)
        for event in dispatcher.events
    )
    assert uow.committed is True


async def test_kernel_rolls_back_when_ledger_posting_fails() -> None:
    """Kernel leaves the Unit of Work uncommitted when posting fails."""
    invoice = build_invoice()
    uow = FakeAccountingUnitOfWork(invoice=invoice, fail_ledger=True)
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerPostingFailedException):
        await service.record_sales_invoice(invoice.id)

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_expense_creates_journal_ledger_and_balances() -> None:
    """Approved expense posting creates journal, ledger entries, and balances."""
    expense = build_expense()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(expense=expense)
    service = build_service(uow, dispatcher)

    journal = await service.record_expense(expense.id)

    assert journal.status == JournalStatus.POSTED
    assert journal.description == "Expense EXP-0001"
    assert len(journal.lines) == EXPENSE_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == EXPENSE_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == EXPENSE_POSTING_ENTRY_COUNT
    assert {entry.source_module for entry in uow.ledgers.entries} == {"expenses"}
    assert uow.committed is True


async def test_expense_posting_uses_chart_lookup() -> None:
    """Expense posting resolves required accounts from the chart of accounts."""
    expense = build_expense()
    uow = FakeAccountingUnitOfWork(expense=expense)
    service = build_service(uow, CapturingEventDispatcher())

    await service.record_expense(expense.id)

    assert uow.chart_of_accounts.requested_codes == ["5600", "2000", "1050"]


async def test_expense_posting_publishes_events() -> None:
    """Expense posting publishes accounting pipeline events."""
    expense = build_expense()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(expense=expense)
    service = build_service(uow, dispatcher)

    await service.record_expense(expense.id)

    assert any(isinstance(event, JournalPostedEvent) for event in dispatcher.events)
    assert any(isinstance(event, LedgerPostedEvent) for event in dispatcher.events)
    assert any(
        isinstance(event, AccountBalanceUpdatedEvent)
        for event in dispatcher.events
    )
    assert any(
        isinstance(event, AccountingExpensePostedEvent)
        for event in dispatcher.events
    )


async def test_expense_payment_creates_journal_and_updates_balances() -> None:
    """Paid expense payment creates ledger entries and updates balances."""
    expense = build_expense(status=ExpenseStatus.PAID)
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(expense=expense)
    service = build_service(uow, dispatcher)

    journal = await service.record_expense_payment(expense.id)

    assert journal.status == JournalStatus.POSTED
    assert len(journal.lines) == EXPENSE_PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == EXPENSE_PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == EXPENSE_PAYMENT_POSTING_ENTRY_COUNT
    assert any(
        isinstance(event, AccountingExpensePaymentPostedEvent)
        for event in dispatcher.events
    )
    assert uow.committed is True


async def test_expense_kernel_rolls_back_when_ledger_posting_fails() -> None:
    """Expense kernel leaves the Unit of Work uncommitted when posting fails."""
    expense = build_expense()
    uow = FakeAccountingUnitOfWork(expense=expense, fail_ledger=True)
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerPostingFailedException):
        await service.record_expense(expense.id)

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_purchase_invoice_creates_journal_ledger_and_balances() -> None:
    """Approved purchase posting creates journal, ledger entries, and balances."""
    purchase = build_purchase()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(purchase=purchase)
    service = build_service(uow, dispatcher)

    journal = await service.record_purchase_invoice(purchase.id)

    assert journal.status == JournalStatus.POSTED
    assert journal.description == "Purchase Invoice PUR-0001"
    assert len(journal.lines) == PURCHASE_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == PURCHASE_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == PURCHASE_POSTING_ENTRY_COUNT
    assert {entry.source_module for entry in uow.ledgers.entries} == {"purchases"}
    assert uow.committed is True


async def test_purchase_accounting_uses_chart_lookup() -> None:
    """Purchase posting resolves required accounts from chart of accounts."""
    purchase = build_purchase()
    uow = FakeAccountingUnitOfWork(purchase=purchase)
    service = build_service(uow, CapturingEventDispatcher())

    await service.record_purchase_invoice(purchase.id)

    assert uow.chart_of_accounts.requested_codes == ["5000", "2000", "1050"]


async def test_purchase_posting_publishes_events() -> None:
    """Purchase posting publishes accounting pipeline events."""
    purchase = build_purchase()
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(purchase=purchase)
    service = build_service(uow, dispatcher)

    await service.record_purchase_invoice(purchase.id)

    assert any(isinstance(event, JournalPostedEvent) for event in dispatcher.events)
    assert any(isinstance(event, LedgerPostedEvent) for event in dispatcher.events)
    assert any(
        isinstance(event, AccountBalanceUpdatedEvent)
        for event in dispatcher.events
    )
    assert any(
        isinstance(event, AccountingPurchasePostedEvent)
        for event in dispatcher.events
    )


async def test_supplier_payment_creates_journal_and_updates_balances() -> None:
    """Paid purchase payment creates ledger entries and updates balances."""
    purchase = build_purchase(status=PurchaseStatus.PAID)
    dispatcher = CapturingEventDispatcher()
    uow = FakeAccountingUnitOfWork(purchase=purchase)
    service = build_service(uow, dispatcher)

    journal = await service.record_supplier_payment(purchase.id)

    assert journal.status == JournalStatus.POSTED
    assert len(journal.lines) == PURCHASE_PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.ledgers.entries) == PURCHASE_PAYMENT_POSTING_ENTRY_COUNT
    assert len(uow.account_balances.balances) == PURCHASE_PAYMENT_POSTING_ENTRY_COUNT
    assert any(
        isinstance(event, AccountingPurchasePaymentPostedEvent)
        for event in dispatcher.events
    )
    assert uow.committed is True


async def test_purchase_kernel_rolls_back_when_ledger_posting_fails() -> None:
    """Purchase kernel leaves the Unit of Work uncommitted when posting fails."""
    purchase = build_purchase()
    uow = FakeAccountingUnitOfWork(purchase=purchase, fail_ledger=True)
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(LedgerPostingFailedException):
        await service.record_purchase_invoice(purchase.id)

    assert uow.committed is False
    assert uow.rolled_back is True
