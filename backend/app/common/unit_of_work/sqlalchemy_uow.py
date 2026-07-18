"""SQLAlchemy Unit of Work implementation."""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.unit_of_work.interface import UnitOfWork
from app.modules.accounting.balances.repository import AccountBalanceRepository
from app.modules.accounting.chart_of_accounts.repository import (
    ChartOfAccountsRepository,
)
from app.modules.accounting.financial_statements.repository import (
    FinancialStatementRepository,
)
from app.modules.accounting.journal.repository import JournalRepository
from app.modules.accounting.ledger.repository import LedgerRepository
from app.modules.accounting.trial_balance.repository import TrialBalanceRepository
from app.modules.business.repository import (
    BusinessMembershipRepository,
    BusinessRepository,
)
from app.modules.expenses.repository import (
    ExpenseLineRepository,
    ExpenseRepository,
    VendorRepository,
)
from app.modules.identity.repository import (
    IdentityPermissionRepository,
    IdentityRefreshTokenRepository,
    IdentityRoleRepository,
    IdentityUserRepository,
)
from app.modules.purchases.repository import (
    PurchaseInvoiceLineRepository,
    PurchaseInvoiceRepository,
    SupplierRepository,
)
from app.modules.sales.repository import (
    CustomerRepository,
    PaymentRepository,
    SalesInvoiceRepository,
)

SessionFactory = Callable[[], AsyncSession]


class SQLAlchemyUnitOfWork(UnitOfWork):
    """Coordinate repositories inside a single SQLAlchemy transaction."""

    def __init__(self, session_factory: SessionFactory) -> None:
        """Initialize with a dependency-injected async session factory."""
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False
        self.users: IdentityUserRepository
        self.roles: IdentityRoleRepository
        self.permissions: IdentityPermissionRepository
        self.refresh_tokens: IdentityRefreshTokenRepository
        self.businesses: BusinessRepository
        self.business_memberships: BusinessMembershipRepository
        self.chart_of_accounts: ChartOfAccountsRepository
        self.journals: JournalRepository
        self.ledgers: LedgerRepository
        self.account_balances: AccountBalanceRepository
        self.trial_balances: TrialBalanceRepository
        self.financial_statements: FinancialStatementRepository
        self.customers: CustomerRepository
        self.sales_invoices: SalesInvoiceRepository
        self.payments: PaymentRepository
        self.vendors: VendorRepository
        self.expenses: ExpenseRepository
        self.expense_lines: ExpenseLineRepository
        self.suppliers: SupplierRepository
        self.purchase_invoices: PurchaseInvoiceRepository
        self.purchase_invoice_lines: PurchaseInvoiceLineRepository

    async def __aenter__(self) -> Self:
        """Open a session and bind repositories to the transaction scope."""
        self._session = self._session_factory()
        self._committed = False
        self.users = IdentityUserRepository(self._session)
        self.roles = IdentityRoleRepository(self._session)
        self.permissions = IdentityPermissionRepository(self._session)
        self.refresh_tokens = IdentityRefreshTokenRepository(self._session)
        self.businesses = BusinessRepository(self._session)
        self.business_memberships = BusinessMembershipRepository(self._session)
        self.chart_of_accounts = ChartOfAccountsRepository(self._session)
        self.journals = JournalRepository(self._session)
        self.ledgers = LedgerRepository(self._session)
        self.account_balances = AccountBalanceRepository(self._session)
        self.trial_balances = TrialBalanceRepository(self.account_balances)
        self.financial_statements = FinancialStatementRepository(
            self.trial_balances
        )
        self.customers = CustomerRepository(self._session)
        self.sales_invoices = SalesInvoiceRepository(self._session)
        self.payments = PaymentRepository(self._session)
        self.vendors = VendorRepository(self._session)
        self.expenses = ExpenseRepository(self._session)
        self.expense_lines = ExpenseLineRepository(self._session)
        self.suppliers = SupplierRepository(self._session)
        self.purchase_invoices = PurchaseInvoiceRepository(self._session)
        self.purchase_invoice_lines = PurchaseInvoiceLineRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback uncommitted work on exit and always close the session."""
        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        """Commit the current transaction."""
        session = self._get_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        session = self._get_session()
        await session.rollback()
        self._committed = False

    def _get_session(self) -> AsyncSession:
        """Return the active session or raise when outside a scope."""
        if self._session is None:
            raise RuntimeError("Unit of Work is not active")
        return self._session
