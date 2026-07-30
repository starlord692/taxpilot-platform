"""Domain service adapters for approved assistant actions."""

import uuid
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.actions.enums import AssistantActionType
from app.modules.assistant.actions.exceptions import AssistantActionValidationException
from app.modules.business.api.context import BusinessContext
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseResponse,
    VendorCreate,
    VendorResponse,
)
from app.modules.purchases.schemas import PurchaseInvoiceCreate, PurchaseInvoiceResponse
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    InvoiceCreateRequest,
    InvoiceResponse,
    PaymentCreateRequest,
    PaymentResponse,
)


class DomainActionResult(BaseModel):
    """Normalized result returned by deterministic domain services."""

    model_config = ConfigDict(extra="forbid")

    erp_record_type: str
    erp_record_id: uuid.UUID | None = None
    domain_service: str
    payload: dict[str, object] = Field(default_factory=dict)


class DomainActionAdapter(Protocol):
    """Adapter that delegates approved actions to deterministic domain services."""

    async def execute(
        self,
        *,
        action_type: AssistantActionType,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        """Execute an approved action through an existing domain service."""
        ...


class SalesInvoiceActionService(Protocol):
    """Sales invoice service behavior required by assistant actions."""

    async def create_invoice(
        self,
        request: InvoiceCreateRequest,
        *,
        customer_request: CustomerCreateRequest | None = None,
    ) -> InvoiceResponse:
        """Create a sales invoice through the Sales bounded context."""
        ...


class PurchaseActionService(Protocol):
    """Purchase service behavior required by assistant actions."""

    async def create_purchase(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
    ) -> PurchaseInvoiceResponse:
        """Create a purchase invoice through the Purchases bounded context."""
        ...


class ExpenseActionService(Protocol):
    """Expense service behavior required by assistant actions."""

    async def create_expense(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
    ) -> ExpenseResponse:
        """Create an expense through the Expenses bounded context."""
        ...


class VendorActionService(Protocol):
    """Vendor service behavior required by assistant actions."""

    async def create_vendor(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
    ) -> VendorResponse:
        """Create a vendor through the Expenses bounded context."""
        ...


class PaymentActionService(Protocol):
    """Payment service behavior required by assistant actions."""

    async def record_payment(self, request: PaymentCreateRequest) -> PaymentResponse:
        """Record a customer payment through the Sales bounded context."""
        ...


class DomainServiceActionAdapter:
    """Delegate approved assistant actions to existing deterministic services."""

    def __init__(
        self,
        *,
        sales_invoice_service: SalesInvoiceActionService,
        purchase_service: PurchaseActionService,
        expense_service: ExpenseActionService,
        vendor_service: VendorActionService,
        payment_service: PaymentActionService,
    ) -> None:
        """Initialize domain service dependencies."""
        self._sales_invoice_service = sales_invoice_service
        self._purchase_service = purchase_service
        self._expense_service = expense_service
        self._vendor_service = vendor_service
        self._payment_service = payment_service

    async def execute(
        self,
        *,
        action_type: AssistantActionType,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        """Execute one approved action through its owning domain service."""
        if action_type == AssistantActionType.SALES_INVOICE_CREATE_DRAFT:
            return await self._create_sales_invoice(payload, business_context)
        if action_type == AssistantActionType.PURCHASE_INVOICE_CREATE_DRAFT:
            return await self._create_purchase_invoice(payload, business_context)
        if action_type == AssistantActionType.EXPENSE_CREATE_DRAFT:
            return await self._create_expense(payload, business_context)
        if action_type == AssistantActionType.VENDOR_CREATE_DRAFT:
            return await self._create_vendor(payload, business_context)
        if action_type == AssistantActionType.PAYMENT_RECORD:
            return await self._record_payment(payload)
        raise AssistantActionValidationException(
            "Assistant action type is not supported by the domain adapter",
            details={"action_type": action_type.value},
        )

    async def _create_sales_invoice(
        self,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        data = self._payload_data(payload)
        data["business_id"] = business_context.business_id
        customer_payload = data.pop("customer", None)
        customer_request = (
            CustomerCreateRequest.model_validate(customer_payload)
            if customer_payload is not None
            else None
        )
        response = await self._sales_invoice_service.create_invoice(
            InvoiceCreateRequest.model_validate(data),
            customer_request=customer_request,
        )
        return self._result(
            erp_record_type="sales_invoice",
            domain_service="SalesInvoiceService",
            response=response,
        )

    async def _create_purchase_invoice(
        self,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        data = self._payload_data(payload)
        response = await self._purchase_service.create_purchase(
            PurchaseInvoiceCreate.model_validate(data),
            business_id=business_context.business_id,
        )
        return self._result(
            erp_record_type="purchase_invoice",
            domain_service="PurchaseService",
            response=response,
        )

    async def _create_expense(
        self,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        data = self._payload_data(payload)
        response = await self._expense_service.create_expense(
            ExpenseCreate.model_validate(data),
            business_id=business_context.business_id,
        )
        return self._result(
            erp_record_type="expense",
            domain_service="ExpenseService",
            response=response,
        )

    async def _create_vendor(
        self,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        data = self._payload_data(payload)
        response = await self._vendor_service.create_vendor(
            VendorCreate.model_validate(data),
            business_id=business_context.business_id,
        )
        return self._result(
            erp_record_type="vendor",
            domain_service="VendorService",
            response=response,
        )

    async def _record_payment(self, payload: dict[str, object]) -> DomainActionResult:
        data = self._payload_data(payload)
        response = await self._payment_service.record_payment(
            PaymentCreateRequest.model_validate(data)
        )
        return self._result(
            erp_record_type="payment",
            domain_service="PaymentService",
            response=response,
        )

    def _payload_data(self, payload: dict[str, object]) -> dict[str, object]:
        """Return the validated action payload body."""
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise AssistantActionValidationException(
                "Assistant action payload data must be an object"
            )
        return dict(cast(dict[str, object], data))

    def _result(
        self,
        *,
        erp_record_type: str,
        domain_service: str,
        response: BaseModel,
    ) -> DomainActionResult:
        """Normalize a domain response for assistant action audit records."""
        payload = response.model_dump(mode="json")
        erp_record_id = getattr(response, "id", None)
        return DomainActionResult(
            erp_record_type=erp_record_type,
            erp_record_id=(
                erp_record_id if isinstance(erp_record_id, uuid.UUID) else None
            ),
            domain_service=domain_service,
            payload=payload,
        )


class UnsupportedDomainActionAdapter:
    """Default adapter used when no domain-service executor is configured."""

    async def execute(
        self,
        *,
        action_type: AssistantActionType,
        payload: dict[str, object],
        business_context: BusinessContext,
    ) -> DomainActionResult:
        """Reject execution without a permissioned domain adapter."""
        _ = payload
        _ = business_context
        raise AssistantActionValidationException(
            "No domain service adapter is configured for assistant actions",
            details={"action_type": action_type.value},
        )
