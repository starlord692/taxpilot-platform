"""Purchase invoice Pydantic schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.purchases.models import PurchaseStatus
from app.modules.purchases.schemas.purchase_line import (
    PurchaseInvoiceLineCreate,
    PurchaseInvoiceLineResponse,
    PurchaseInvoiceLineUpdate,
)
from app.modules.purchases.schemas.supplier import (
    PurchaseResponseBase,
    SupplierResponse,
)
from app.modules.purchases.validators import (
    validate_attachment_count,
    validate_non_negative_decimal,
    validate_optional_text,
    validate_purchase_dates,
    validate_purchase_total,
    validate_total_at_least_subtotal,
)


class PurchaseInvoiceCreate(BaseModel):
    """Request schema for creating a purchase invoice."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID = Field(
        description="Supplier UUID.",
        examples=[str(uuid.uuid4())],
    )
    invoice_number: str = Field(
        description="Supplier invoice number.",
        examples=["SUP-INV-0001"],
        min_length=1,
        max_length=50,
    )
    invoice_date: date = Field(
        description="Supplier invoice date.",
        examples=["2026-06-01"],
    )
    due_date: date | None = Field(
        default=None,
        description="Invoice due date.",
        examples=["2026-06-30"],
    )
    subtotal: Decimal = Field(description="Purchase subtotal.", examples=["1000.00"])
    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Purchase tax amount.",
        examples=["180.00"],
    )
    total_amount: Decimal = Field(
        description="Purchase total amount.",
        examples=["1180.00"],
    )
    notes: str | None = Field(default=None, description="Optional purchase notes.")
    attachment_count: int = Field(
        default=0,
        description="Number of attachments linked to the purchase invoice.",
        examples=[1],
    )
    status: PurchaseStatus = Field(
        default=PurchaseStatus.DRAFT,
        description="Purchase invoice lifecycle status.",
        examples=[PurchaseStatus.DRAFT],
    )
    lines: list[PurchaseInvoiceLineCreate] = Field(
        default_factory=list,
        description="Purchase invoice line items.",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        """Validate notes when present."""
        return validate_optional_text(value, field_name="notes", max_length=2000)

    @field_validator("subtotal", "tax_amount", "total_amount")
    @classmethod
    def validate_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative purchase amount."""
        return validate_non_negative_decimal(value, field_name="amount")

    @field_validator("attachment_count")
    @classmethod
    def validate_attachment_count(cls, value: int) -> int:
        """Validate attachment count."""
        return validate_attachment_count(value)

    @model_validator(mode="after")
    def validate_dates_and_totals(self) -> Self:
        """Validate purchase date ordering and totals."""
        validate_purchase_dates(
            invoice_date=self.invoice_date,
            due_date=self.due_date,
        )
        validate_total_at_least_subtotal(
            subtotal=self.subtotal,
            total_amount=self.total_amount,
        )
        validate_purchase_total(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
        )
        return self


class PurchaseInvoiceUpdate(BaseModel):
    """Request schema for updating a purchase invoice."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = Field(
        default=None,
        description="Updated supplier UUID.",
        examples=[str(uuid.uuid4())],
    )
    invoice_number: str | None = Field(
        default=None,
        description="Updated supplier invoice number.",
        examples=["SUP-INV-0002"],
        max_length=50,
    )
    invoice_date: date | None = Field(
        default=None,
        description="Updated invoice date.",
        examples=["2026-06-01"],
    )
    due_date: date | None = Field(
        default=None,
        description="Updated due date.",
        examples=["2026-06-30"],
    )
    subtotal: Decimal | None = Field(default=None, description="Updated subtotal.")
    tax_amount: Decimal | None = Field(default=None, description="Updated tax amount.")
    total_amount: Decimal | None = Field(
        default=None,
        description="Updated total amount.",
    )
    notes: str | None = Field(default=None, description="Updated purchase notes.")
    attachment_count: int | None = Field(
        default=None,
        description="Updated attachment count.",
        examples=[1],
    )
    status: PurchaseStatus | None = Field(
        default=None,
        description="Updated purchase invoice lifecycle status.",
        examples=[PurchaseStatus.APPROVED],
    )
    lines: list[PurchaseInvoiceLineUpdate] | None = Field(
        default=None,
        description="Updated purchase invoice line items.",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        """Validate notes when present."""
        return validate_optional_text(value, field_name="notes", max_length=2000)

    @field_validator("subtotal", "tax_amount", "total_amount")
    @classmethod
    def validate_amounts(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional non-negative purchase amount."""
        if value is None:
            return None
        return validate_non_negative_decimal(value, field_name="amount")

    @field_validator("attachment_count")
    @classmethod
    def validate_attachment_count(cls, value: int | None) -> int | None:
        """Validate optional attachment count."""
        if value is None:
            return None
        return validate_attachment_count(value)

    @model_validator(mode="after")
    def validate_dates_and_totals(self) -> Self:
        """Validate date ordering and totals when supplied."""
        validate_purchase_dates(
            invoice_date=self.invoice_date,
            due_date=self.due_date,
        )
        validate_total_at_least_subtotal(
            subtotal=self.subtotal,
            total_amount=self.total_amount,
        )
        validate_purchase_total(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
        )
        return self


class PurchaseInvoiceListResponse(PurchaseResponseBase):
    """Compact response schema for purchase invoice lists."""

    id: uuid.UUID = Field(description="Purchase invoice UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    supplier_id: uuid.UUID = Field(description="Supplier UUID.")
    purchase_number: str = Field(description="Business-scoped purchase number.")
    invoice_number: str = Field(description="Supplier invoice number.")
    invoice_date: date = Field(description="Supplier invoice date.")
    due_date: date | None = Field(default=None, description="Invoice due date.")
    status: PurchaseStatus = Field(description="Purchase invoice lifecycle status.")
    total_amount: Decimal = Field(description="Purchase total amount.")
    attachment_count: int = Field(description="Purchase attachment count.")


class PurchaseInvoiceResponse(PurchaseInvoiceListResponse):
    """Response schema for a purchase invoice."""

    subtotal: Decimal = Field(description="Purchase subtotal.")
    tax_amount: Decimal = Field(description="Purchase tax amount.")
    notes: str | None = Field(default=None, description="Purchase notes.")
    supplier: SupplierResponse | None = Field(
        default=None,
        description="Purchase invoice supplier.",
    )
    lines: list[PurchaseInvoiceLineResponse] = Field(
        default_factory=list,
        description="Purchase invoice line items.",
    )
