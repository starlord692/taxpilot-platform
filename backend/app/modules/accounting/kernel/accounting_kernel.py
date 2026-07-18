"""Reusable Accounting Kernel for module integrations."""

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.events import EventDispatcher
from app.modules.accounting.balances.events import AccountBalanceUpdatedEvent
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import Account
from app.modules.accounting.journal.events import JournalPostedEvent
from app.modules.accounting.journal.exceptions import (
    JournalAccountInactiveException,
    JournalUnbalancedException,
    JournalValidationFailedException,
)
from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
)
from app.modules.accounting.kernel.events import (
    AccountingExpensePaymentPostedEvent,
    AccountingExpensePostedEvent,
    AccountingInvoicePostedEvent,
    AccountingPaymentPostedEvent,
    AccountingPurchasePaymentPostedEvent,
    AccountingPurchasePostedEvent,
)
from app.modules.accounting.ledger.events import LedgerPostedEvent
from app.modules.accounting.ledger.exceptions import (
    LedgerAlreadyPostedException,
    LedgerPostingFailedException,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry
from app.modules.expenses.exceptions import (
    ExpenseNotFoundException,
    InvalidExpenseStatusException,
)
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.purchases.exceptions import (
    InvalidPurchaseStatusException,
    PurchaseNotFoundException,
)
from app.modules.purchases.models import PurchaseInvoice, PurchaseStatus
from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesInvoiceNotFoundException,
    SalesPaymentNotFoundException,
)
from app.modules.sales.models import (
    InvoiceStatus,
    Payment,
    PaymentMethod,
    SalesInvoice,
)

ZERO_AMOUNT = Decimal("0.00")
MINIMUM_JOURNAL_LINES = 2
ACCOUNTS_RECEIVABLE_CODE = "1020"
BANK_CODE = "1010"
CASH_CODE = "1000"
SALES_REVENUE_CODE = "4000"
TAX_PAYABLE_CODE = "2010"
ACCOUNTS_PAYABLE_CODE = "2000"
INPUT_TAX_CODE = "1050"
PURCHASES_EXPENSE_CODE = "5000"
EXPENSE_CATEGORY_ACCOUNT_CODES = {
    ExpenseCategory.TRAVEL: "5800",
    ExpenseCategory.OFFICE: "5500",
    ExpenseCategory.RENT: "5200",
    ExpenseCategory.UTILITIES: "5300",
    ExpenseCategory.MARKETING: "5700",
    ExpenseCategory.SALARY: "5100",
    ExpenseCategory.PROFESSIONAL_FEES: "5910",
    ExpenseCategory.SOFTWARE: "5600",
    ExpenseCategory.HARDWARE: "5500",
    ExpenseCategory.OTHER: "5900",
}


class AccountingKernelInvoiceRepository(Protocol):
    """Invoice persistence behavior required by the accounting kernel."""

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return an invoice by UUID."""
        ...


class AccountingKernelPaymentRepository(Protocol):
    """Payment persistence behavior required by the accounting kernel."""

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return a payment by UUID."""
        ...


class AccountingKernelExpenseRepository(Protocol):
    """Expense persistence behavior required by the accounting kernel."""

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return an expense by UUID."""
        ...


class AccountingKernelPurchaseRepository(Protocol):
    """Purchase persistence behavior required by the accounting kernel."""

    async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
        """Return a purchase invoice by UUID."""
        ...


class AccountingKernelChartRepository(Protocol):
    """Chart of accounts behavior required by the accounting kernel."""

    async def get_account_by_code(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
    ) -> Account | None:
        """Return a business account by account code."""
        ...


class AccountingKernelJournalRepository(Protocol):
    """Journal persistence behavior required by the accounting kernel."""

    async def add(self, entity: JournalEntry) -> JournalEntry:
        """Persist a journal entry."""
        ...

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        """Mark a journal as posted."""
        ...


class AccountingKernelLedgerRepository(Protocol):
    """Ledger persistence behavior required by the accounting kernel."""

    async def create_entries(
        self,
        entries: list[GeneralLedgerEntry],
    ) -> list[GeneralLedgerEntry]:
        """Persist ledger entries."""
        ...

    async def exists_for_journal(self, journal_id: uuid.UUID) -> bool:
        """Return whether a journal already has ledger entries."""
        ...


class AccountingKernelBalanceRepository(Protocol):
    """Balance persistence behavior required by the accounting kernel."""

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        """Create or return an account balance."""
        ...

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        """Update a balance with ledger deltas."""
        ...


class AccountingKernelUnitOfWork(Protocol):
    """Unit of Work contract required by the accounting kernel."""

    sales_invoices: AccountingKernelInvoiceRepository
    payments: AccountingKernelPaymentRepository
    expenses: AccountingKernelExpenseRepository
    purchase_invoices: AccountingKernelPurchaseRepository
    chart_of_accounts: AccountingKernelChartRepository
    journals: AccountingKernelJournalRepository
    ledgers: AccountingKernelLedgerRepository
    account_balances: AccountingKernelBalanceRepository

    async def __aenter__(self) -> "AccountingKernelUnitOfWork":
        """Enter the accounting transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the accounting transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit accounting changes."""
        ...


UnitOfWorkFactory = Callable[[], AccountingKernelUnitOfWork]


class AccountingKernelService:
    """Coordinate accounting postings for upstream business modules."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize the accounting kernel with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher

    async def record_sales_invoice(self, invoice_id: uuid.UUID) -> JournalEntry:
        """Post an issued sales invoice through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            invoice = await uow.sales_invoices.get_by_id(invoice_id)
            if invoice is None:
                raise SalesInvoiceNotFoundException(
                    "Invoice not found",
                    details={"invoice_id": str(invoice_id)},
                )
            if invoice.status != InvoiceStatus.ISSUED:
                raise SalesInvalidInvoiceStatusException(
                    "Only issued invoices can be posted to accounting",
                    details={
                        "invoice_id": str(invoice_id),
                        "status": invoice.status.value,
                    },
                )

            accounts = await self._load_invoice_accounts(uow, invoice.business_id)
            journal = await self._create_invoice_journal(uow, invoice, accounts)
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="sales",
                source_entity="sales_invoice",
                source_entity_id=invoice.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingInvoicePostedEvent(
                    invoice_id=invoice.id,
                    journal_id=journal.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()
            return journal

    async def record_customer_payment(self, payment_id: uuid.UUID) -> JournalEntry:
        """Post a customer payment through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            payment = await uow.payments.get_by_id(payment_id)
            if payment is None:
                raise SalesPaymentNotFoundException(
                    "Payment not found",
                    details={"payment_id": str(payment_id)},
                )
            invoice = await uow.sales_invoices.get_by_id(payment.invoice_id)
            if invoice is None:
                raise SalesInvoiceNotFoundException(
                    "Invoice not found",
                    details={"invoice_id": str(payment.invoice_id)},
                )

            accounts = await self._load_payment_accounts(
                uow,
                invoice.business_id,
                payment.payment_method,
            )
            journal = await self._create_payment_journal(
                uow,
                invoice,
                payment,
                accounts,
            )
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="sales",
                source_entity="payment",
                source_entity_id=payment.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingPaymentPostedEvent(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    journal_id=journal.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()
            return journal

    async def record_expense(self, expense_id: uuid.UUID) -> JournalEntry:
        """Post an approved expense through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            expense = await uow.expenses.get_by_id(expense_id)
            if expense is None:
                raise ExpenseNotFoundException(
                    "Expense not found",
                    details={"expense_id": str(expense_id)},
                )
            if expense.status != ExpenseStatus.APPROVED:
                raise InvalidExpenseStatusException(
                    "Only approved expenses can be posted to accounting",
                    details={
                        "expense_id": str(expense_id),
                        "status": expense.status.value,
                    },
                )

            accounts = await self._load_expense_accounts(uow, expense)
            journal = await self._create_expense_journal(uow, expense, accounts)
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="expenses",
                source_entity="expense",
                source_entity_id=expense.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingExpensePostedEvent(
                    expense_id=expense.id,
                    journal_id=journal.id,
                    business_id=expense.business_id,
                )
            )
            await uow.commit()
            return journal

    async def record_expense_payment(self, expense_id: uuid.UUID) -> JournalEntry:
        """Post a paid expense payment through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            expense = await uow.expenses.get_by_id(expense_id)
            if expense is None:
                raise ExpenseNotFoundException(
                    "Expense not found",
                    details={"expense_id": str(expense_id)},
                )
            if expense.status != ExpenseStatus.PAID:
                raise InvalidExpenseStatusException(
                    "Only paid expenses can have payment accounting posted",
                    details={
                        "expense_id": str(expense_id),
                        "status": expense.status.value,
                    },
                )

            accounts = await self._load_expense_payment_accounts(
                uow,
                expense.business_id,
            )
            journal = await self._create_expense_payment_journal(
                uow,
                expense,
                accounts,
            )
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="expenses",
                source_entity="expense_payment",
                source_entity_id=expense.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingExpensePaymentPostedEvent(
                    expense_id=expense.id,
                    journal_id=journal.id,
                    business_id=expense.business_id,
                )
            )
            await uow.commit()
            return journal

    async def record_purchase_invoice(
        self,
        purchase_id: uuid.UUID,
    ) -> JournalEntry:
        """Post an approved purchase through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            purchase = await uow.purchase_invoices.get_by_id(purchase_id)
            if purchase is None:
                raise PurchaseNotFoundException(
                    "Purchase invoice not found",
                    details={"purchase_id": str(purchase_id)},
                )
            if purchase.status != PurchaseStatus.APPROVED:
                raise InvalidPurchaseStatusException(
                    "Only approved purchases can be posted to accounting",
                    details={
                        "purchase_id": str(purchase_id),
                        "status": purchase.status.value,
                    },
                )

            accounts = await self._load_purchase_accounts(uow, purchase)
            journal = await self._create_purchase_journal(uow, purchase, accounts)
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="purchases",
                source_entity="purchase_invoice",
                source_entity_id=purchase.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingPurchasePostedEvent(
                    purchase_id=purchase.id,
                    journal_id=journal.id,
                    business_id=purchase.business_id,
                )
            )
            await uow.commit()
            return journal

    async def record_supplier_payment(
        self,
        purchase_id: uuid.UUID,
    ) -> JournalEntry:
        """Post a paid purchase payment through journal, ledger, and balances."""
        async with self._unit_of_work_factory() as uow:
            purchase = await uow.purchase_invoices.get_by_id(purchase_id)
            if purchase is None:
                raise PurchaseNotFoundException(
                    "Purchase invoice not found",
                    details={"purchase_id": str(purchase_id)},
                )
            if purchase.status != PurchaseStatus.PAID:
                raise InvalidPurchaseStatusException(
                    "Only paid purchases can have supplier payment accounting posted",
                    details={
                        "purchase_id": str(purchase_id),
                        "status": purchase.status.value,
                    },
                )

            accounts = await self._load_supplier_payment_accounts(
                uow,
                purchase.business_id,
            )
            journal = await self._create_supplier_payment_journal(
                uow,
                purchase,
                accounts,
            )
            ledger_entries = await self._post_journal_to_ledger(
                uow,
                journal,
                source_module="purchases",
                source_entity="supplier_payment",
                source_entity_id=purchase.id,
            )
            await self._apply_balances(uow, ledger_entries)
            await self._event_dispatcher.dispatch(
                AccountingPurchasePaymentPostedEvent(
                    purchase_id=purchase.id,
                    journal_id=journal.id,
                    business_id=purchase.business_id,
                )
            )
            await uow.commit()
            return journal

    async def _load_invoice_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        business_id: uuid.UUID,
    ) -> dict[str, Account]:
        """Load accounts needed for sales invoice posting."""
        accounts = {
            ACCOUNTS_RECEIVABLE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=ACCOUNTS_RECEIVABLE_CODE,
            ),
            SALES_REVENUE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=SALES_REVENUE_CODE,
            ),
            TAX_PAYABLE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=TAX_PAYABLE_CODE,
            ),
        }
        return accounts

    async def _load_payment_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        business_id: uuid.UUID,
        payment_method: PaymentMethod,
    ) -> dict[str, Account]:
        """Load accounts needed for customer payment posting."""
        cash_or_bank_code = (
            CASH_CODE if payment_method == PaymentMethod.CASH else BANK_CODE
        )
        return {
            cash_or_bank_code: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=cash_or_bank_code,
            ),
            ACCOUNTS_RECEIVABLE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=ACCOUNTS_RECEIVABLE_CODE,
            ),
        }

    async def _load_expense_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        expense: Expense,
    ) -> dict[str, Account]:
        """Load accounts needed for approved expense posting."""
        expense_account_code = EXPENSE_CATEGORY_ACCOUNT_CODES[expense.category]
        accounts = {
            expense_account_code: await self._get_required_account(
                uow,
                business_id=expense.business_id,
                account_code=expense_account_code,
            ),
            ACCOUNTS_PAYABLE_CODE: await self._get_required_account(
                uow,
                business_id=expense.business_id,
                account_code=ACCOUNTS_PAYABLE_CODE,
            ),
        }
        if expense.tax_amount > ZERO_AMOUNT:
            accounts[INPUT_TAX_CODE] = await self._get_required_account(
                uow,
                business_id=expense.business_id,
                account_code=INPUT_TAX_CODE,
            )
        return accounts

    async def _load_expense_payment_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        business_id: uuid.UUID,
    ) -> dict[str, Account]:
        """Load accounts needed for expense payment posting."""
        return {
            ACCOUNTS_PAYABLE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=ACCOUNTS_PAYABLE_CODE,
            ),
            BANK_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=BANK_CODE,
            ),
        }

    async def _load_purchase_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        purchase: PurchaseInvoice,
    ) -> dict[str, Account]:
        """Load accounts needed for approved purchase posting."""
        accounts = {
            PURCHASES_EXPENSE_CODE: await self._get_required_account(
                uow,
                business_id=purchase.business_id,
                account_code=PURCHASES_EXPENSE_CODE,
            ),
            ACCOUNTS_PAYABLE_CODE: await self._get_required_account(
                uow,
                business_id=purchase.business_id,
                account_code=ACCOUNTS_PAYABLE_CODE,
            ),
        }
        if purchase.tax_amount > ZERO_AMOUNT:
            accounts[INPUT_TAX_CODE] = await self._get_required_account(
                uow,
                business_id=purchase.business_id,
                account_code=INPUT_TAX_CODE,
            )
        return accounts

    async def _load_supplier_payment_accounts(
        self,
        uow: AccountingKernelUnitOfWork,
        business_id: uuid.UUID,
    ) -> dict[str, Account]:
        """Load accounts needed for supplier payment posting."""
        return {
            ACCOUNTS_PAYABLE_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=ACCOUNTS_PAYABLE_CODE,
            ),
            BANK_CODE: await self._get_required_account(
                uow,
                business_id=business_id,
                account_code=BANK_CODE,
            ),
        }

    async def _get_required_account(
        self,
        uow: AccountingKernelUnitOfWork,
        *,
        business_id: uuid.UUID,
        account_code: str,
    ) -> Account:
        """Return an active account or raise a validation error."""
        account = await uow.chart_of_accounts.get_account_by_code(
            business_id=business_id,
            account_code=account_code,
        )
        if account is None:
            raise JournalValidationFailedException(
                "Required accounting account was not found",
                details={
                    "business_id": str(business_id),
                    "account_code": account_code,
                },
            )
        if not account.is_active:
            raise JournalAccountInactiveException(
                "Required accounting account is inactive",
                details={
                    "business_id": str(business_id),
                    "account_code": account_code,
                },
            )
        return account

    async def _create_invoice_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        invoice: SalesInvoice,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post a sales invoice journal entry."""
        lines = [
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_RECEIVABLE_CODE].id,
                account=accounts[ACCOUNTS_RECEIVABLE_CODE],
                debit=invoice.total_amount,
                credit=ZERO_AMOUNT,
                description=f"Accounts receivable for {invoice.invoice_number}",
            ),
            JournalEntryLine(
                account_id=accounts[SALES_REVENUE_CODE].id,
                account=accounts[SALES_REVENUE_CODE],
                debit=ZERO_AMOUNT,
                credit=invoice.taxable_amount,
                description=f"Sales revenue for {invoice.invoice_number}",
            ),
        ]
        for component_name, amount in self._tax_components(
            invoice.lines,
            fallback_tax_amount=invoice.tax_amount,
        ).items():
            if amount > ZERO_AMOUNT:
                lines.append(
                    JournalEntryLine(
                        account_id=accounts[TAX_PAYABLE_CODE].id,
                        account=accounts[TAX_PAYABLE_CODE],
                        debit=ZERO_AMOUNT,
                        credit=amount,
                        description=(
                            f"Output {component_name} for {invoice.invoice_number}"
                        ),
                    )
                )
        journal = JournalEntry(
            business_id=invoice.business_id,
            journal_number=f"SINV-{invoice.invoice_number}",
            transaction_date=invoice.invoice_date,
            reference=invoice.invoice_number,
            description=f"Sales Invoice {invoice.invoice_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _create_payment_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        invoice: SalesInvoice,
        payment: Payment,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post a customer payment journal entry."""
        cash_or_bank_code = (
            CASH_CODE if payment.payment_method == PaymentMethod.CASH else BANK_CODE
        )
        lines = [
            JournalEntryLine(
                account_id=accounts[cash_or_bank_code].id,
                account=accounts[cash_or_bank_code],
                debit=payment.amount,
                credit=ZERO_AMOUNT,
                description=f"Customer payment for {invoice.invoice_number}",
            ),
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_RECEIVABLE_CODE].id,
                account=accounts[ACCOUNTS_RECEIVABLE_CODE],
                debit=ZERO_AMOUNT,
                credit=payment.amount,
                description=f"Accounts receivable payment for {invoice.invoice_number}",
            ),
        ]
        journal = JournalEntry(
            business_id=invoice.business_id,
            journal_number=f"PAY-{payment.id.hex[:12].upper()}",
            transaction_date=payment.payment_date,
            reference=payment.reference_number,
            description=f"Customer Payment {invoice.invoice_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _create_expense_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        expense: Expense,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post an approved expense journal entry."""
        expense_account_code = EXPENSE_CATEGORY_ACCOUNT_CODES[expense.category]
        lines = [
            JournalEntryLine(
                account_id=accounts[expense_account_code].id,
                account=accounts[expense_account_code],
                debit=expense.subtotal,
                credit=ZERO_AMOUNT,
                description=f"Expense account for {expense.expense_number}",
            )
        ]
        for component_name, amount in self._tax_components(
            expense.lines,
            fallback_tax_amount=expense.tax_amount,
        ).items():
            if amount > ZERO_AMOUNT:
                lines.append(
                    JournalEntryLine(
                        account_id=accounts[INPUT_TAX_CODE].id,
                        account=accounts[INPUT_TAX_CODE],
                        debit=amount,
                        credit=ZERO_AMOUNT,
                        description=(
                            f"Input {component_name} for {expense.expense_number}"
                        ),
                    )
                )
        lines.append(
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_PAYABLE_CODE].id,
                account=accounts[ACCOUNTS_PAYABLE_CODE],
                debit=ZERO_AMOUNT,
                credit=expense.total_amount,
                description=f"Accounts payable for {expense.expense_number}",
            )
        )
        journal = JournalEntry(
            business_id=expense.business_id,
            journal_number=f"EXP-{expense.expense_number}",
            transaction_date=expense.expense_date,
            reference=expense.expense_number,
            description=f"Expense {expense.expense_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _create_expense_payment_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        expense: Expense,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post an expense payment journal entry."""
        lines = [
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_PAYABLE_CODE].id,
                account=accounts[ACCOUNTS_PAYABLE_CODE],
                debit=expense.total_amount,
                credit=ZERO_AMOUNT,
                description=f"Accounts payable payment for {expense.expense_number}",
            ),
            JournalEntryLine(
                account_id=accounts[BANK_CODE].id,
                account=accounts[BANK_CODE],
                debit=ZERO_AMOUNT,
                credit=expense.total_amount,
                description=f"Bank payment for {expense.expense_number}",
            ),
        ]
        journal = JournalEntry(
            business_id=expense.business_id,
            journal_number=f"EPAY-{expense.expense_number}",
            transaction_date=expense.expense_date,
            reference=expense.expense_number,
            description=f"Expense Payment {expense.expense_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _create_purchase_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        purchase: PurchaseInvoice,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post an approved purchase journal entry."""
        lines = [
            JournalEntryLine(
                account_id=accounts[PURCHASES_EXPENSE_CODE].id,
                account=accounts[PURCHASES_EXPENSE_CODE],
                debit=purchase.subtotal,
                credit=ZERO_AMOUNT,
                description=f"Purchase expense for {purchase.purchase_number}",
            )
        ]
        for component_name, amount in self._tax_components(
            purchase.lines,
            fallback_tax_amount=purchase.tax_amount,
        ).items():
            if amount > ZERO_AMOUNT:
                lines.append(
                    JournalEntryLine(
                        account_id=accounts[INPUT_TAX_CODE].id,
                        account=accounts[INPUT_TAX_CODE],
                        debit=amount,
                        credit=ZERO_AMOUNT,
                        description=(
                            f"Input {component_name} for {purchase.purchase_number}"
                        ),
                    )
                )
        lines.append(
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_PAYABLE_CODE].id,
                account=accounts[ACCOUNTS_PAYABLE_CODE],
                debit=ZERO_AMOUNT,
                credit=purchase.total_amount,
                description=f"Accounts payable for {purchase.purchase_number}",
            )
        )
        journal = JournalEntry(
            business_id=purchase.business_id,
            journal_number=f"PINV-{purchase.purchase_number}",
            transaction_date=purchase.invoice_date,
            reference=purchase.invoice_number,
            description=f"Purchase Invoice {purchase.purchase_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _create_supplier_payment_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        purchase: PurchaseInvoice,
        accounts: dict[str, Account],
    ) -> JournalEntry:
        """Create and post a supplier payment journal entry."""
        lines = [
            JournalEntryLine(
                account_id=accounts[ACCOUNTS_PAYABLE_CODE].id,
                account=accounts[ACCOUNTS_PAYABLE_CODE],
                debit=purchase.total_amount,
                credit=ZERO_AMOUNT,
                description=f"Accounts payable payment for {purchase.purchase_number}",
            ),
            JournalEntryLine(
                account_id=accounts[BANK_CODE].id,
                account=accounts[BANK_CODE],
                debit=ZERO_AMOUNT,
                credit=purchase.total_amount,
                description=f"Bank payment for {purchase.purchase_number}",
            ),
        ]
        journal = JournalEntry(
            business_id=purchase.business_id,
            journal_number=f"PPAY-{purchase.purchase_number}",
            transaction_date=purchase.due_date or purchase.invoice_date,
            reference=purchase.invoice_number,
            description=f"Supplier Payment {purchase.purchase_number}",
            status=JournalStatus.DRAFT,
            lines=lines,
        )
        return await self._persist_and_post_journal(uow, journal)

    async def _persist_and_post_journal(
        self,
        uow: AccountingKernelUnitOfWork,
        journal: JournalEntry,
    ) -> JournalEntry:
        """Persist, validate, and mark a journal as posted."""
        journal = await uow.journals.add(journal)
        self._validate_journal(journal)
        journal = await uow.journals.mark_posted(
            journal,
            posting_date=datetime.now(tz=UTC).date(),
        )
        await self._event_dispatcher.dispatch(JournalPostedEvent(journal_id=journal.id))
        return journal

    async def _post_journal_to_ledger(
        self,
        uow: AccountingKernelUnitOfWork,
        journal: JournalEntry,
        *,
        source_module: str,
        source_entity: str,
        source_entity_id: uuid.UUID,
    ) -> list[GeneralLedgerEntry]:
        """Create immutable ledger entries for a posted journal."""
        if await uow.ledgers.exists_for_journal(journal.id):
            raise LedgerAlreadyPostedException(
                "Journal entry has already been posted to the ledger",
                details={"journal_id": str(journal.id)},
            )
        if journal.posting_date is None:
            raise LedgerPostingFailedException(
                "Posted journal entry must have a posting date",
                details={"journal_id": str(journal.id)},
            )
        entries = [
            GeneralLedgerEntry(
                business_id=journal.business_id,
                journal_entry_id=journal.id,
                journal_line_id=line.id,
                account_id=line.account_id,
                transaction_date=journal.transaction_date,
                posting_date=journal.posting_date,
                debit=line.debit,
                credit=line.credit,
                description=line.description or journal.description,
                source_module=source_module,
                source_entity=source_entity,
                source_entity_id=source_entity_id,
            )
            for line in journal.lines
        ]
        try:
            entries = await uow.ledgers.create_entries(entries)
        except Exception as exc:
            raise LedgerPostingFailedException(
                "Ledger posting failed",
                details={"journal_id": str(journal.id)},
            ) from exc
        await self._event_dispatcher.dispatch(
            LedgerPostedEvent(
                journal_id=journal.id,
                ledger_entry_count=len(entries),
            )
        )
        return entries

    async def _apply_balances(
        self,
        uow: AccountingKernelUnitOfWork,
        ledger_entries: list[GeneralLedgerEntry],
    ) -> list[AccountBalance]:
        """Apply ledger entries to the account balance read model."""
        balances: list[AccountBalance] = []
        grouped: dict[uuid.UUID, list[GeneralLedgerEntry]] = {}
        for entry in ledger_entries:
            grouped.setdefault(entry.account_id, []).append(entry)

        last_posted_at = datetime.now(tz=UTC)
        for account_id, entries in grouped.items():
            first_entry = entries[0]
            balance = await uow.account_balances.create_if_missing(
                business_id=first_entry.business_id,
                account_id=account_id,
            )
            balances.append(
                await uow.account_balances.update_balance(
                    balance,
                    debit_delta=sum((entry.debit for entry in entries), ZERO_AMOUNT),
                    credit_delta=sum((entry.credit for entry in entries), ZERO_AMOUNT),
                    last_posted_at=last_posted_at,
                )
            )

        if ledger_entries:
            await self._event_dispatcher.dispatch(
                AccountBalanceUpdatedEvent(
                    journal_id=ledger_entries[0].journal_entry_id,
                    business_id=ledger_entries[0].business_id,
                    account_ids=list(grouped.keys()),
                )
            )
        return balances

    def _validate_journal(self, journal: JournalEntry) -> None:
        """Validate basic double-entry rules before posting."""
        total_debit = sum((line.debit for line in journal.lines), ZERO_AMOUNT)
        total_credit = sum((line.credit for line in journal.lines), ZERO_AMOUNT)
        if len(journal.lines) < MINIMUM_JOURNAL_LINES:
            raise JournalValidationFailedException(
                "Journal entry must include at least two lines"
            )
        if total_debit != total_credit:
            raise JournalUnbalancedException(
                "Journal entry debits and credits must balance",
                details={
                    "total_debit": str(total_debit),
                    "total_credit": str(total_credit),
                },
            )
        if any(
            line.debit < ZERO_AMOUNT or line.credit < ZERO_AMOUNT
            for line in journal.lines
        ):
            raise JournalValidationFailedException(
                "Journal entry cannot include negative debit or credit values"
            )
        if not any(line.debit > ZERO_AMOUNT for line in journal.lines):
            raise JournalValidationFailedException(
                "Journal entry must include at least one debit"
            )
        if not any(line.credit > ZERO_AMOUNT for line in journal.lines):
            raise JournalValidationFailedException(
                "Journal entry must include at least one credit"
            )
        if any(
            line.account is None or not line.account.is_active
            for line in journal.lines
        ):
            raise JournalAccountInactiveException(
                "Journal entry references an inactive account"
            )

    def _tax_components(
        self,
        lines: Iterable[object],
        *,
        fallback_tax_amount: Decimal,
    ) -> dict[str, Decimal]:
        """Return aggregate GST components from source lines."""
        components = {
            "CGST": ZERO_AMOUNT,
            "SGST": ZERO_AMOUNT,
            "IGST": ZERO_AMOUNT,
            "CESS": ZERO_AMOUNT,
        }
        for line in lines:
            components["CGST"] += getattr(line, "cgst_amount", ZERO_AMOUNT)
            components["SGST"] += getattr(line, "sgst_amount", ZERO_AMOUNT)
            components["IGST"] += getattr(line, "igst_amount", ZERO_AMOUNT)
            components["CESS"] += getattr(line, "cess_amount", ZERO_AMOUNT)
        if sum(components.values(), ZERO_AMOUNT) == ZERO_AMOUNT:
            components["GST"] = fallback_tax_amount
        return components
