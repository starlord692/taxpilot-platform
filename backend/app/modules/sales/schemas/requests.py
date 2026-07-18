"""Sales request schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.sales.models import InvoiceStatus, PaymentMethod
from app.modules.sales.validators import (
    validate_customer_name,
    validate_email,
    validate_gstin,
    validate_invoice_dates,
    validate_non_negative_decimal,
    validate_pan,
    validate_phone,
    validate_positive_decimal,
)


class CustomerCreateRequest(BaseModel):
    """Request schema for creating a customer."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(
        description="Business UUID.",
        examples=[str(uuid.uuid4())],
    )
    customer_code: str = Field(
        description="Business-scoped customer code.",
        examples=["CUST-0001"],
        min_length=1,
        max_length=50,
    )
    name: str = Field(
        description="Customer display name.",
        examples=["Aarav Enterprises"],
    )
    email: str | None = Field(
        default=None,
        description="Customer email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Customer phone number in E.164 format.",
        examples=["+919876543210"],
    )
    gstin: str | None = Field(
        default=None,
        description="Indian Goods and Services Tax Identification Number.",
        examples=["29ABCDE1234F1Z5"],
    )
    pan: str | None = Field(
        default=None,
        description="Indian Permanent Account Number.",
        examples=["ABCDE1234F"],
    )
    billing_address: str | None = Field(
        default=None,
        description="Customer billing address.",
        examples=["42 Residency Road, Bengaluru"],
    )
    shipping_address: str | None = Field(
        default=None,
        description="Customer shipping address.",
        examples=["42 Residency Road, Bengaluru"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate customer name."""
        return validate_customer_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Validate email when present."""
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Validate phone when present."""
        return validate_phone(value)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        """Validate GSTIN when present."""
        return validate_gstin(value)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        """Validate PAN when present."""
        return validate_pan(value)


class CustomerUpdateRequest(BaseModel):
    """Request schema for updating a customer."""

    model_config = ConfigDict(extra="forbid")

    customer_code: str | None = Field(
        default=None,
        description="Updated business-scoped customer code.",
        examples=["CUST-0002"],
        max_length=50,
    )
    name: str | None = Field(
        default=None,
        description="Updated customer display name.",
        examples=["Aarav Enterprises"],
    )
    email: str | None = Field(
        default=None,
        description="Updated customer email address.",
        examples=["billing@example.com"],
    )
    phone: str | None = Field(
        default=None,
        description="Updated customer phone number in E.164 format.",
        examples=["+919876543210"],
    )
    gstin: str | None = Field(
        default=None,
        description="Updated GSTIN.",
        examples=["29ABCDE1234F1Z5"],
    )
    pan: str | None = Field(
        default=None,
        description="Updated PAN.",
        examples=["ABCDE1234F"],
    )
    billing_address: str | None = Field(
        default=None,
        description="Updated billing address.",
    )
    shipping_address: str | None = Field(
        default=None,
        description="Updated shipping address.",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the customer is active.",
        examples=[True],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Validate customer name when present."""
        if value is None:
            return None
        return validate_customer_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Validate email when present."""
        return validate_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Validate phone when present."""
        return validate_phone(value)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        """Validate GSTIN when present."""
        return validate_gstin(value)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        """Validate PAN when present."""
        return validate_pan(value)


class InvoiceLineRequest(BaseModel):
    """Request schema for an invoice line."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description="Line item description.",
        examples=["Monthly bookkeeping"],
        min_length=1,
        max_length=255,
    )
    quantity: Decimal = Field(description="Line quantity.", examples=["2.00"])
    unit_price: Decimal = Field(description="Unit price.", examples=["500.00"])
    discount: Decimal = Field(
        default=Decimal("0.00"),
        description="Line discount amount.",
        examples=["50.00"],
    )
    tax_rate: Decimal = Field(
        default=Decimal("0.00"),
        description="Line tax rate percentage.",
        examples=["18.00"],
    )
    cgst_amount: Decimal = Field(default=Decimal("0.00"), examples=["85.50"])
    sgst_amount: Decimal = Field(default=Decimal("0.00"), examples=["85.50"])
    igst_amount: Decimal = Field(default=Decimal("0.00"), examples=["0.00"])
    cess_amount: Decimal = Field(default=Decimal("0.00"), examples=["0.00"])
    line_total: Decimal = Field(description="Line total amount.", examples=["1121.00"])

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        """Validate positive quantity."""
        return validate_positive_decimal(value, field_name="quantity")

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, value: Decimal) -> Decimal:
        """Validate positive unit price."""
        return validate_positive_decimal(value, field_name="unit_price")

    @field_validator(
        "discount",
        "tax_rate",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "cess_amount",
        "line_total",
    )
    @classmethod
    def validate_non_negative_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative decimal values."""
        return validate_non_negative_decimal(value, field_name="amount")


class InvoiceCreateRequest(BaseModel):
    """Request schema for creating a sales invoice."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(
        description="Business UUID.",
        examples=[str(uuid.uuid4())],
    )
    customer_id: uuid.UUID = Field(
        description="Customer UUID.",
        examples=[str(uuid.uuid4())],
    )
    invoice_number: str = Field(
        description="Business-scoped invoice number.",
        examples=["INV-0001"],
        min_length=1,
        max_length=50,
    )
    invoice_date: date = Field(
        description="Invoice issue date.",
        examples=["2026-04-01"],
    )
    due_date: date | None = Field(
        default=None,
        description="Invoice due date.",
        examples=["2026-04-30"],
    )
    status: InvoiceStatus = Field(
        default=InvoiceStatus.DRAFT,
        description="Invoice lifecycle status.",
        examples=[InvoiceStatus.DRAFT],
    )
    subtotal: Decimal = Field(description="Invoice subtotal.", examples=["1000.00"])
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Invoice-level discount amount.",
        examples=["50.00"],
    )
    taxable_amount: Decimal = Field(
        description="Taxable invoice amount.",
        examples=["950.00"],
    )
    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Invoice tax amount.",
        examples=["171.00"],
    )
    total_amount: Decimal = Field(
        description="Invoice total amount.",
        examples=["1121.00"],
    )
    notes: str | None = Field(default=None, description="Optional invoice notes.")
    lines: list[InvoiceLineRequest] = Field(
        description="Invoice line items.",
        min_length=1,
    )

    @field_validator(
        "subtotal",
        "discount_amount",
        "taxable_amount",
        "tax_amount",
        "total_amount",
    )
    @classmethod
    def validate_invoice_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative invoice amount."""
        return validate_non_negative_decimal(value, field_name="amount")

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Validate invoice date ordering."""
        validate_invoice_dates(
            invoice_date=self.invoice_date,
            due_date=self.due_date,
        )
        return self


class InvoiceUpdateRequest(BaseModel):
    """Request schema for updating a sales invoice."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None = Field(
        default=None,
        description="Updated invoice number.",
        examples=["INV-0002"],
        max_length=50,
    )
    invoice_date: date | None = Field(
        default=None,
        description="Updated invoice date.",
        examples=["2026-04-01"],
    )
    due_date: date | None = Field(
        default=None,
        description="Updated due date.",
        examples=["2026-04-30"],
    )
    status: InvoiceStatus | None = Field(
        default=None,
        description="Updated invoice status.",
        examples=[InvoiceStatus.ISSUED],
    )
    subtotal: Decimal | None = Field(default=None, description="Updated subtotal.")
    discount_amount: Decimal | None = Field(
        default=None,
        description="Updated discount amount.",
    )
    taxable_amount: Decimal | None = Field(
        default=None,
        description="Updated taxable amount.",
    )
    tax_amount: Decimal | None = Field(default=None, description="Updated tax amount.")
    total_amount: Decimal | None = Field(
        default=None,
        description="Updated total amount.",
    )
    notes: str | None = Field(default=None, description="Updated invoice notes.")
    lines: list[InvoiceLineRequest] | None = Field(
        default=None,
        description="Updated invoice line items.",
    )

    @field_validator(
        "subtotal",
        "discount_amount",
        "taxable_amount",
        "tax_amount",
        "total_amount",
    )
    @classmethod
    def validate_invoice_amounts(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional non-negative invoice amount."""
        if value is None:
            return None
        return validate_non_negative_decimal(value, field_name="amount")

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Validate invoice date ordering when both dates are present."""
        validate_invoice_dates(
            invoice_date=self.invoice_date,
            due_date=self.due_date,
        )
        return self


class PaymentCreateRequest(BaseModel):
    """Request schema for creating an invoice payment."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID = Field(
        description="Invoice UUID.",
        examples=[str(uuid.uuid4())],
    )
    payment_date: date = Field(description="Payment date.", examples=["2026-04-10"])
    amount: Decimal = Field(description="Payment amount.", examples=["500.00"])
    payment_method: PaymentMethod = Field(
        description="Payment method.",
        examples=[PaymentMethod.UPI],
    )
    reference_number: str | None = Field(
        default=None,
        description="External payment reference number.",
        examples=["UPI-123"],
        max_length=100,
    )
    notes: str | None = Field(default=None, description="Optional payment notes.")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        """Validate positive payment amount."""
        return validate_positive_decimal(value, field_name="amount")
