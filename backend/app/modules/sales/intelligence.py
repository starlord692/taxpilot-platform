"""Deterministic, advisory intelligence for canonical Sales invoices."""

import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from statistics import median
from typing import Protocol, cast

from pydantic import BaseModel, Field

from app.common.events import EventDispatcher
from app.modules.sales.events import InvoiceIntelligenceEvaluatedEvent
from app.modules.sales.exceptions import (
    SalesInvoiceNotFoundException,
    SalesInvoiceValidationException,
)
from app.modules.sales.financial_rules import (
    SalesFinancialRulesEngine,
    StoredFinancialInvoice,
)

DUPLICATE_DATE_WINDOW_DAYS = 7
DUPLICATE_SCORE_THRESHOLD = 50
NOT_READY_MAXIMUM_PASSED_CHECKS = 2


class RecommendationCategory(StrEnum):
    DUPLICATE = "duplicate"
    GST = "gst"
    PRICING = "pricing"
    DISCOUNT = "discount"
    CUSTOMER = "customer"
    CATALOG = "catalog"
    COMPLETENESS = "completeness"
    FINANCIAL = "financial"
    POLICY = "policy"


class RecommendationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AutomationReadiness(StrEnum):
    READY = "ready"
    PARTIALLY_READY = "partially_ready"
    NOT_READY = "not_ready"


class InvoiceRecommendation(BaseModel):
    category: RecommendationCategory
    severity: RecommendationSeverity
    confidence: int = Field(ge=0, le=100)
    explanation: str
    suggested_action: str
    related_invoice_id: uuid.UUID | None = None


class ReadinessCheck(BaseModel):
    name: str
    ready: bool
    explanation: str


class AutomationReadinessAssessment(BaseModel):
    status: AutomationReadiness
    confidence: int = Field(ge=0, le=100)
    checks: list[ReadinessCheck]


class InvoiceIntelligenceResponse(BaseModel):
    invoice_id: uuid.UUID
    recommendations: list[InvoiceRecommendation]
    automation_readiness: AutomationReadinessAssessment


class IntelligenceLine(Protocol):
    catalog_item_id: uuid.UUID | None
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal


class IntelligenceCustomer(Protocol):
    email: str | None
    phone: str | None
    gstin: str | None
    billing_address: str | None


class IntelligenceInvoice(Protocol):
    id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    invoice_date: date
    total_amount: Decimal
    currency: str | None
    lines: Sequence[IntelligenceLine]
    customer: IntelligenceCustomer


class IntelligenceCatalogItem(Protocol):
    id: uuid.UUID
    gst_rate: Decimal
    cess_rate: Decimal
    selling_price: Decimal
    hsn_code: str | None
    sac_code: str | None


class IntelligenceEngine:
    """Pure recommendation engine; never mutates analyzed records."""

    def __init__(
        self,
        financial_rules: SalesFinancialRulesEngine | None = None,
    ) -> None:
        self._financial = financial_rules or SalesFinancialRulesEngine()

    def evaluate(
        self,
        invoice: IntelligenceInvoice,
        *,
        catalog: dict[uuid.UUID, IntelligenceCatalogItem],
        history: Sequence[IntelligenceInvoice] = (),
        business_settings_complete: bool,
        business_gst_registered: bool,
    ) -> InvoiceIntelligenceResponse:
        recommendations = [
            *self._duplicates(invoice, history),
            *self._gst(invoice, catalog, business_gst_registered),
            *self._pricing(invoice, catalog, history),
            *self._discounts(invoice),
            *self._customer(invoice, business_gst_registered),
            *self._completeness(invoice, catalog),
        ]
        financially_consistent = self._financially_consistent(invoice)
        if not financially_consistent:
            recommendations.append(
                self._recommendation(
                    RecommendationCategory.FINANCIAL,
                    RecommendationSeverity.CRITICAL,
                    100,
                    "Stored invoice totals do not reconcile with its line values.",
                    "Review the invoice and recalculate it before issuing.",
                )
            )
        readiness = self._readiness(
            invoice,
            catalog,
            business_settings_complete=business_settings_complete,
            business_gst_registered=business_gst_registered,
            financially_consistent=financially_consistent,
        )
        return InvoiceIntelligenceResponse(
            invoice_id=invoice.id,
            recommendations=recommendations,
            automation_readiness=readiness,
        )

    def _duplicates(
        self,
        invoice: IntelligenceInvoice,
        history: Sequence[IntelligenceInvoice],
    ) -> list[InvoiceRecommendation]:
        current_items = {line.catalog_item_id for line in invoice.lines}
        results = []
        for candidate in history:
            if (
                candidate.id == invoice.id
                or candidate.customer_id != invoice.customer_id
            ):
                continue
            score = 25
            reasons = ["same customer"]
            if candidate.total_amount == invoice.total_amount:
                score += 30
                reasons.append("same total")
            days = abs((candidate.invoice_date - invoice.invoice_date).days)
            if days == 0:
                score += 20
                reasons.append("same invoice date")
            elif days <= DUPLICATE_DATE_WINDOW_DAYS:
                score += 10
                reasons.append("invoice dates within seven days")
            candidate_items = {line.catalog_item_id for line in candidate.lines}
            if current_items and current_items == candidate_items:
                score += 25
                reasons.append("same catalog items")
            elif current_items & candidate_items:
                score += 10
                reasons.append("overlapping catalog items")
            if score >= DUPLICATE_SCORE_THRESHOLD:
                results.append(
                    self._recommendation(
                        RecommendationCategory.DUPLICATE,
                        RecommendationSeverity.WARNING,
                        min(score, 100),
                        f"Potential duplicate of {candidate.invoice_number}: "
                        + ", ".join(reasons)
                        + ".",
                        "Compare both invoices before continuing.",
                        candidate.id,
                    )
                )
        return sorted(results, key=lambda item: item.confidence, reverse=True)

    def _gst(
        self,
        invoice: IntelligenceInvoice,
        catalog: dict[uuid.UUID, IntelligenceCatalogItem],
        registered: bool,
    ) -> list[InvoiceRecommendation]:
        results = []
        rates = {line.tax_rate for line in invoice.lines}
        if len(rates) > 1:
            results.append(
                self._recommendation(
                    RecommendationCategory.GST,
                    RecommendationSeverity.INFO,
                    100,
                    "The invoice contains multiple GST rates.",
                    "Confirm each catalog item's tax classification.",
                )
            )
        for line in invoice.lines:
            item = catalog.get(line.catalog_item_id) if line.catalog_item_id else None
            if item is None:
                continue
            if line.tax_rate != item.gst_rate:
                results.append(
                    self._recommendation(
                        RecommendationCategory.GST,
                        RecommendationSeverity.WARNING,
                        100,
                        "An invoice line GST rate differs from its catalog tax rate.",
                        "Review the catalog tax classification and recalculate "
                        "the invoice.",
                    )
                )
            if registered and not item.hsn_code and not item.sac_code:
                results.append(
                    self._recommendation(
                        RecommendationCategory.GST,
                        RecommendationSeverity.WARNING,
                        95,
                        "A taxable catalog item has no HSN or SAC classification.",
                        "Complete the catalog item's tax classification.",
                    )
                )
            has_intra = line.cgst_amount > 0 or line.sgst_amount > 0
            if has_intra and line.igst_amount > 0:
                results.append(
                    self._recommendation(
                        RecommendationCategory.GST,
                        RecommendationSeverity.CRITICAL,
                        100,
                        "A line contains both intra-state and inter-state GST "
                        "components.",
                        "Review place of supply and recalculate tax before issuing.",
                    )
                )
        return results

    def _pricing(
        self,
        invoice: IntelligenceInvoice,
        catalog: dict[uuid.UUID, IntelligenceCatalogItem],
        history: Sequence[IntelligenceInvoice],
    ) -> list[InvoiceRecommendation]:
        prices: defaultdict[uuid.UUID, list[Decimal]] = defaultdict(list)
        for previous in history:
            for line in previous.lines:
                if line.catalog_item_id is not None and line.unit_price > 0:
                    prices[line.catalog_item_id].append(line.unit_price)
        results = []
        for line in invoice.lines:
            if line.unit_price == 0:
                results.append(
                    self._recommendation(
                        RecommendationCategory.PRICING,
                        RecommendationSeverity.WARNING,
                        100,
                        "A catalog line has a zero unit price.",
                        "Confirm that the item is intentionally free of charge.",
                    )
                )
                continue
            comparison = prices.get(line.catalog_item_id or uuid.UUID(int=0), [])
            baseline = Decimal(str(median(comparison))) if comparison else None
            if baseline and self._deviation(line.unit_price, baseline) >= Decimal(
                "0.25"
            ):
                results.append(
                    self._recommendation(
                        RecommendationCategory.PRICING,
                        RecommendationSeverity.WARNING,
                        85,
                        "The unit price differs by at least 25% from its historical "
                        "median.",
                        "Confirm the price before issuing the invoice.",
                    )
                )
            item = catalog.get(line.catalog_item_id) if line.catalog_item_id else None
            if (
                item is not None
                and item.selling_price > 0
                and self._deviation(line.unit_price, item.selling_price)
                >= Decimal("0.25")
            ):
                results.append(
                    self._recommendation(
                        RecommendationCategory.PRICING,
                        RecommendationSeverity.INFO,
                        90,
                        "The unit price differs by at least 25% from the catalog "
                        "price.",
                        "Confirm the agreed customer price.",
                    )
                )
        return results

    def _discounts(self, invoice: IntelligenceInvoice) -> list[InvoiceRecommendation]:
        results = []
        for line in invoice.lines:
            gross = line.quantity * line.unit_price
            if gross > 0 and line.discount / gross >= Decimal("0.30"):
                results.append(
                    self._recommendation(
                        RecommendationCategory.DISCOUNT,
                        RecommendationSeverity.WARNING,
                        95,
                        "A line discount is at least 30% of its gross value.",
                        "Confirm that the discount is authorized.",
                    )
                )
        return results

    def _customer(
        self, invoice: IntelligenceInvoice, gst_registered: bool
    ) -> list[InvoiceRecommendation]:
        missing = []
        if not invoice.customer.email:
            missing.append("email")
        if not invoice.customer.phone:
            missing.append("phone")
        if not invoice.customer.billing_address:
            missing.append("billing address")
        if gst_registered and not invoice.customer.gstin:
            missing.append("GSTIN")
        if not missing:
            return []
        return [
            self._recommendation(
                RecommendationCategory.CUSTOMER,
                RecommendationSeverity.WARNING,
                100,
                "Customer information is incomplete: " + ", ".join(missing) + ".",
                "Complete the customer profile before relying on automation.",
            )
        ]

    def _completeness(
        self,
        invoice: IntelligenceInvoice,
        catalog: dict[uuid.UUID, IntelligenceCatalogItem],
    ) -> list[InvoiceRecommendation]:
        if invoice.lines and all(
            line.catalog_item_id is not None and line.catalog_item_id in catalog
            for line in invoice.lines
        ):
            return []
        return [
            self._recommendation(
                RecommendationCategory.CATALOG,
                RecommendationSeverity.CRITICAL,
                100,
                "One or more invoice lines are not mapped to available catalog items.",
                "Map every line to a canonical catalog item.",
            )
        ]

    def _financially_consistent(self, invoice: IntelligenceInvoice) -> bool:
        try:
            self._financial.reconcile(cast(StoredFinancialInvoice, invoice))
        except SalesInvoiceValidationException:
            return False
        return True

    def _readiness(
        self,
        invoice: IntelligenceInvoice,
        catalog: dict[uuid.UUID, IntelligenceCatalogItem],
        *,
        business_settings_complete: bool,
        business_gst_registered: bool,
        financially_consistent: bool,
    ) -> AutomationReadinessAssessment:
        checks = [
            ReadinessCheck(
                name="customer_mapped", ready=True, explanation="Customer is mapped."
            ),
            ReadinessCheck(
                name="catalog_mapped",
                ready=bool(invoice.lines)
                and all(line.catalog_item_id in catalog for line in invoice.lines),
                explanation="Every line must map to an available catalog item.",
            ),
            ReadinessCheck(
                name="business_settings_complete",
                ready=business_settings_complete,
                explanation="Business currency settings must be available.",
            ),
            ReadinessCheck(
                name="gst_complete",
                ready=(not business_gst_registered) or bool(invoice.customer.gstin),
                explanation=(
                    "GST-registered businesses require customer GST information."
                ),
            ),
            ReadinessCheck(
                name="financially_consistent",
                ready=financially_consistent,
                explanation="Stored financial values must reconcile.",
            ),
        ]
        passed = sum(check.ready for check in checks)
        status = (
            AutomationReadiness.READY
            if passed == len(checks)
            else AutomationReadiness.NOT_READY
            if passed <= NOT_READY_MAXIMUM_PASSED_CHECKS
            else AutomationReadiness.PARTIALLY_READY
        )
        return AutomationReadinessAssessment(
            status=status,
            confidence=round(passed / len(checks) * 100),
            checks=checks,
        )

    @staticmethod
    def _deviation(value: Decimal, baseline: Decimal) -> Decimal:
        return abs(value - baseline) / baseline if baseline else Decimal("0")

    @staticmethod
    def _recommendation(
        category: RecommendationCategory,
        severity: RecommendationSeverity,
        confidence: int,
        explanation: str,
        action: str,
        related_invoice_id: uuid.UUID | None = None,
    ) -> InvoiceRecommendation:
        return InvoiceRecommendation(
            category=category,
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            suggested_action=action,
            related_invoice_id=related_invoice_id,
        )


class IntelligenceInvoiceRepository(Protocol):
    async def get_by_id(self, invoice_id: uuid.UUID) -> IntelligenceInvoice | None: ...
    async def list_intelligence_history(
        self, *, business_id: uuid.UUID, customer_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> Sequence[IntelligenceInvoice]: ...


class IntelligenceCatalogRepository(Protocol):
    async def get_by_ids(
        self, item_ids: set[uuid.UUID]
    ) -> Sequence[IntelligenceCatalogItem]: ...


class IntelligenceBusinessRepository(Protocol):
    async def get_settings(self, business_id: uuid.UUID) -> object | None: ...
    async def get_tax_profile(self, business_id: uuid.UUID) -> object | None: ...


class IntelligenceUnitOfWork(Protocol):
    sales_invoices: IntelligenceInvoiceRepository
    catalog_items: IntelligenceCatalogRepository
    businesses: IntelligenceBusinessRepository

    async def __aenter__(self) -> "IntelligenceUnitOfWork": ...
    async def __aexit__(
        self, exc_type: object, exc: object, traceback: object
    ) -> None: ...


class SalesIntelligenceService:
    """Read-only application service for invoice recommendations."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], IntelligenceUnitOfWork],
        event_dispatcher: EventDispatcher,
        engine: IntelligenceEngine | None = None,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._events = event_dispatcher
        self._engine = engine or IntelligenceEngine()

    async def evaluate(self, invoice_id: uuid.UUID) -> InvoiceIntelligenceResponse:
        async with self._uow_factory() as uow:
            invoice = await uow.sales_invoices.get_by_id(invoice_id)
            if invoice is None:
                raise SalesInvoiceNotFoundException("Invoice not found")
            history = await uow.sales_invoices.list_intelligence_history(
                business_id=invoice.business_id,
                customer_id=invoice.customer_id,
                exclude_id=invoice.id,
            )
            item_ids = {
                line.catalog_item_id
                for line in invoice.lines
                if line.catalog_item_id is not None
            }
            items = await uow.catalog_items.get_by_ids(item_ids)
            settings = await uow.businesses.get_settings(invoice.business_id)
            tax_profile = await uow.businesses.get_tax_profile(invoice.business_id)
        response = self._engine.evaluate(
            invoice,
            catalog={item.id: item for item in items},
            history=history,
            business_settings_complete=bool(
                settings is not None and getattr(settings, "currency", None)
            ),
            business_gst_registered=bool(
                tax_profile is not None
                and getattr(tax_profile, "gst_registered", False)
            ),
        )
        await self._events.dispatch(
            InvoiceIntelligenceEvaluatedEvent(
                invoice.id,
                invoice.business_id,
                len(response.recommendations),
                response.automation_readiness.status.value,
            )
        )
        return response
