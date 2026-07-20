"""Canonical Sales workflow API contracts."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.sales.models import InvoiceStatus


class CanonicalInvoiceLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class CanonicalInvoiceDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_date: date
    due_date: date | None = None
    notes: str | None = None
    round_off: Decimal = Decimal("0")
    lines: list[CanonicalInvoiceLineRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> "CanonicalInvoiceDraftRequest":
        if self.due_date is not None and self.due_date < self.invoice_date:
            raise ValueError("Due date cannot precede invoice date")
        return self


class CanonicalInvoiceDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    round_off: Decimal | None = None
    lines: list[CanonicalInvoiceLineRequest] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_round_off_update(self) -> "CanonicalInvoiceDraftUpdate":
        if self.round_off is not None and self.lines is None:
            raise ValueError(
                "Round-off changes require invoice lines for recalculation"
            )
        if (
            self.invoice_date is not None
            and self.due_date is not None
            and self.due_date < self.invoice_date
        ):
            raise ValueError("Due date cannot precede invoice date")
        return self


class CanonicalInvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    catalog_item_id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal


class CanonicalInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    status: InvoiceStatus
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    round_off: Decimal
    total_amount: Decimal
    notes: str | None
    lines: list[CanonicalInvoiceLineResponse]
