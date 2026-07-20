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
from app.modules.catalog.repository import (
    CatalogItemRepository,
    InventoryItemProfileRepository,
)
from app.modules.documents.automation.repository import AutomationRunRepository
from app.modules.documents.extraction.repository import (
    ExtractedDocumentRepository,
    ExtractedFieldRepository,
    ExtractionReviewRepository,
)
from app.modules.documents.repository import (
    DocumentPageRepository,
    DocumentRepository,
    OCRResultRepository,
)
from app.modules.documents.review.repository import (
    DocumentReviewRepository,
    ReviewDecisionRepository,
    ReviewRevisionRepository,
    ValidationIssueRepository,
)
from app.modules.expenses.repository import (
    ExpenseLineRepository,
    ExpenseRepository,
    VendorRepository,
)
from app.modules.gst.compliance.repository import GSTComplianceRepository
from app.modules.gst.einvoice.repository import (
    EInvoiceRepository,
    EWayBillRepository,
    GSTProviderRepository,
)
from app.modules.gst.repository import (
    GSTRegistrationRepository,
    GSTSettingsRepository,
    GSTTaxRateRepository,
    HSNCodeRepository,
    SACCodeRepository,
)
from app.modules.identity.repository import (
    IdentityPermissionRepository,
    IdentityRefreshTokenRepository,
    IdentityRoleRepository,
    IdentityUserRepository,
)
from app.modules.inventory.repository import (
    ProductRepository,
    StockBalanceRepository,
    StockMovementRepository,
    WarehouseRepository,
)
from app.modules.purchases.repository import (
    PurchaseInvoiceLineRepository,
    PurchaseInvoiceRepository,
    SupplierRepository,
)
from app.modules.sales.repository import (
    CustomerRepository,
    InvoiceNumberSequenceRepository,
    PaymentRepository,
    SalesInvoiceRepository,
)

SessionFactory = Callable[[], AsyncSession]


class SQLAlchemyUnitOfWork(UnitOfWork):
    """Coordinate repositories inside a single SQLAlchemy transaction."""

    def __init__(self, session_factory: SessionFactory) -> None:  # noqa: PLR0915
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
        self.documents: DocumentRepository
        self.document_pages: DocumentPageRepository
        self.ocr_results: OCRResultRepository
        self.extracted_documents: ExtractedDocumentRepository
        self.extracted_fields: ExtractedFieldRepository
        self.extraction_reviews: ExtractionReviewRepository
        self.automation_runs: AutomationRunRepository
        self.validation_issues: ValidationIssueRepository
        self.document_reviews: DocumentReviewRepository
        self.review_revisions: ReviewRevisionRepository
        self.review_decisions: ReviewDecisionRepository
        self.chart_of_accounts: ChartOfAccountsRepository
        self.journals: JournalRepository
        self.ledgers: LedgerRepository
        self.account_balances: AccountBalanceRepository
        self.trial_balances: TrialBalanceRepository
        self.financial_statements: FinancialStatementRepository
        self.customers: CustomerRepository
        self.sales_invoices: SalesInvoiceRepository
        self.invoice_number_sequences: InvoiceNumberSequenceRepository
        self.payments: PaymentRepository
        self.vendors: VendorRepository
        self.expenses: ExpenseRepository
        self.expense_lines: ExpenseLineRepository
        self.suppliers: SupplierRepository
        self.purchase_invoices: PurchaseInvoiceRepository
        self.purchase_invoice_lines: PurchaseInvoiceLineRepository
        self.products: ProductRepository
        self.catalog_items: CatalogItemRepository
        self.inventory_item_profiles: InventoryItemProfileRepository
        self.warehouses: WarehouseRepository
        self.stock_balances: StockBalanceRepository
        self.stock_movements: StockMovementRepository
        self.gst_registrations: GSTRegistrationRepository
        self.gst_tax_rates: GSTTaxRateRepository
        self.hsn_codes: HSNCodeRepository
        self.sac_codes: SACCodeRepository
        self.gst_settings: GSTSettingsRepository
        self.gst_compliance: GSTComplianceRepository
        self.einvoices: EInvoiceRepository
        self.eway_bills: EWayBillRepository
        self.gst_providers: GSTProviderRepository

    async def __aenter__(self) -> Self:  # noqa: PLR0915
        """Open a session and bind repositories to the transaction scope."""
        self._session = self._session_factory()
        self._committed = False
        self.users = IdentityUserRepository(self._session)
        self.roles = IdentityRoleRepository(self._session)
        self.permissions = IdentityPermissionRepository(self._session)
        self.refresh_tokens = IdentityRefreshTokenRepository(self._session)
        self.businesses = BusinessRepository(self._session)
        self.business_memberships = BusinessMembershipRepository(self._session)
        self.documents = DocumentRepository(self._session)
        self.document_pages = DocumentPageRepository(self._session)
        self.ocr_results = OCRResultRepository(self._session)
        self.extracted_documents = ExtractedDocumentRepository(self._session)
        self.extracted_fields = ExtractedFieldRepository(self._session)
        self.extraction_reviews = ExtractionReviewRepository(self._session)
        self.automation_runs = AutomationRunRepository(self._session)
        self.validation_issues = ValidationIssueRepository(self._session)
        self.document_reviews = DocumentReviewRepository(self._session)
        self.review_revisions = ReviewRevisionRepository(self._session)
        self.review_decisions = ReviewDecisionRepository(self._session)
        self.chart_of_accounts = ChartOfAccountsRepository(self._session)
        self.journals = JournalRepository(self._session)
        self.ledgers = LedgerRepository(self._session)
        self.account_balances = AccountBalanceRepository(self._session)
        self.trial_balances = TrialBalanceRepository(self.account_balances)
        self.financial_statements = FinancialStatementRepository(self.trial_balances)
        self.customers = CustomerRepository(self._session)
        self.sales_invoices = SalesInvoiceRepository(self._session)
        self.invoice_number_sequences = InvoiceNumberSequenceRepository(self._session)
        self.payments = PaymentRepository(self._session)
        self.vendors = VendorRepository(self._session)
        self.expenses = ExpenseRepository(self._session)
        self.expense_lines = ExpenseLineRepository(self._session)
        self.suppliers = SupplierRepository(self._session)
        self.purchase_invoices = PurchaseInvoiceRepository(self._session)
        self.purchase_invoice_lines = PurchaseInvoiceLineRepository(self._session)
        self.products = ProductRepository(self._session)
        self.catalog_items = CatalogItemRepository(self._session)
        self.inventory_item_profiles = InventoryItemProfileRepository(self._session)
        self.warehouses = WarehouseRepository(self._session)
        self.stock_balances = StockBalanceRepository(self._session)
        self.stock_movements = StockMovementRepository(self._session)
        self.gst_registrations = GSTRegistrationRepository(self._session)
        self.gst_tax_rates = GSTTaxRateRepository(self._session)
        self.hsn_codes = HSNCodeRepository(self._session)
        self.sac_codes = SACCodeRepository(self._session)
        self.gst_settings = GSTSettingsRepository(self._session)
        self.gst_compliance = GSTComplianceRepository(self._session)
        self.einvoices = EInvoiceRepository(self._session)
        self.eway_bills = EWayBillRepository(self._session)
        self.gst_providers = GSTProviderRepository(self._session)
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
