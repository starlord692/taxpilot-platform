"""Sales response schemas."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.sales.models import InvoiceStatus, PaymentMethod


class SalesResponseBase(BaseModel):
    """Base sales response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CustomerResponse(SalesResponseBase):
    """Response schema for a customer."""

    id: uuid.UUID = Field(description="Customer UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    customer_code: str = Field(description="Business-scoped customer code.")
    name: str = Field(description="Customer display name.")
    email: str | None = Field(default=None, description="Customer email address.")
    phone: str | None = Field(default=None, description="Customer phone number.")
    gstin: str | None = Field(default=None, description="Customer GSTIN.")
    pan: str | None = Field(default=None, description="Customer PAN.")
    billing_address: str | None = Field(
        default=None,
        description="Customer billing address.",
    )
    shipping_address: str | None = Field(
        default=None,
        description="Customer shipping address.",
    )
    is_active: bool = Field(description="Whether the customer is active.")


class InvoiceLineResponse(SalesResponseBase):
    """Response schema for an invoice line."""

    catalog_item_id: uuid.UUID | None = Field(
        default=None, description="Canonical catalog reference when migrated."
    )
    id: uuid.UUID = Field(description="Invoice line UUID.")
    invoice_id: uuid.UUID = Field(description="Invoice UUID.")
    description: str = Field(description="Line item description.")
    quantity: Decimal = Field(description="Line quantity.")
    unit_price: Decimal = Field(description="Unit price.")
    discount: Decimal = Field(description="Line discount amount.")
    tax_rate: Decimal = Field(description="Line tax rate percentage.")
    cgst_amount: Decimal = Field(description="Line CGST amount.")
    sgst_amount: Decimal = Field(description="Line SGST amount.")
    igst_amount: Decimal = Field(description="Line IGST amount.")
    cess_amount: Decimal = Field(description="Line cess amount.")
    line_total: Decimal = Field(description="Line total amount.")

    @field_validator(
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        mode="before",
    )
    @classmethod
    def default_missing_gst_component(cls, value: Decimal | None) -> Decimal:
        """Default legacy missing GST component values to zero."""
        return value or Decimal("0.00")


class PaymentResponse(SalesResponseBase):
    """Response schema for an invoice payment."""

    id: uuid.UUID = Field(description="Payment UUID.")
    invoice_id: uuid.UUID = Field(description="Invoice UUID.")
    payment_date: date = Field(description="Payment date.")
    amount: Decimal = Field(description="Payment amount.")
    payment_method: PaymentMethod = Field(description="Payment method.")
    reference_number: str | None = Field(
        default=None,
        description="External payment reference number.",
    )
    notes: str | None = Field(default=None, description="Payment notes.")


class InvoiceSummaryResponse(SalesResponseBase):
    """Compact response schema for sales invoice lists."""

    id: uuid.UUID = Field(description="Invoice UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    customer_id: uuid.UUID = Field(description="Customer UUID.")
    invoice_number: str = Field(description="Business-scoped invoice number.")
    invoice_date: date = Field(description="Invoice issue date.")
    due_date: date | None = Field(default=None, description="Invoice due date.")
    status: InvoiceStatus = Field(description="Invoice lifecycle status.")
    total_amount: Decimal = Field(description="Invoice total amount.")


class InvoiceResponse(InvoiceSummaryResponse):
    """Full response schema for a sales invoice."""

    round_off: Decimal = Field(
        default=Decimal("0.00"), description="Canonical round-off adjustment."
    )

    @field_validator("round_off", mode="before")
    @classmethod
    def default_legacy_round_off(cls, value: Decimal | None) -> Decimal:
        """Default pre-migration invoice instances to zero round-off."""
        return value or Decimal("0.00")

    subtotal: Decimal = Field(description="Invoice subtotal.")
    discount_amount: Decimal = Field(description="Invoice-level discount amount.")
    taxable_amount: Decimal = Field(description="Taxable invoice amount.")
    tax_amount: Decimal = Field(description="Invoice tax amount.")
    notes: str | None = Field(default=None, description="Invoice notes.")
    lines: list[InvoiceLineResponse] = Field(
        default_factory=list,
        description="Invoice line items.",
    )
    payments: list[PaymentResponse] = Field(
        default_factory=list,
        description="Invoice payments.",
    )
