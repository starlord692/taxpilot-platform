"""Expense Pydantic schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.expenses.models import ExpenseCategory, ExpenseStatus
from app.modules.expenses.schemas.expense_line import (
    ExpenseLineCreate,
    ExpenseLineResponse,
    ExpenseLineUpdate,
)
from app.modules.expenses.schemas.vendor import ExpenseResponseBase, VendorResponse
from app.modules.expenses.validators import (
    validate_attachment_count,
    validate_expense_total,
    validate_non_negative_decimal,
    validate_optional_text,
)


class ExpenseCreate(BaseModel):
    """Request schema for creating an expense."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: uuid.UUID | None = Field(
        default=None,
        description="Optional vendor UUID.",
        examples=[str(uuid.uuid4())],
    )
    expense_date: date = Field(
        description="Expense date.",
        examples=["2026-05-01"],
    )
    category: ExpenseCategory = Field(
        description="Expense category.",
        examples=[ExpenseCategory.SOFTWARE],
    )
    description: str | None = Field(
        default=None,
        description="Expense description.",
        examples=["Accounting software subscription"],
        max_length=255,
    )
    subtotal: Decimal = Field(description="Expense subtotal.", examples=["1000.00"])
    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        description="Expense tax amount.",
        examples=["180.00"],
    )
    total_amount: Decimal = Field(
        description="Expense total amount.",
        examples=["1180.00"],
    )
    notes: str | None = Field(default=None, description="Optional expense notes.")
    attachment_count: int = Field(
        default=0,
        description="Number of attachments linked to the expense.",
        examples=[1],
    )
    status: ExpenseStatus = Field(
        default=ExpenseStatus.DRAFT,
        description="Expense lifecycle status.",
        examples=[ExpenseStatus.DRAFT],
    )
    lines: list[ExpenseLineCreate] = Field(
        default_factory=list,
        description="Expense line items.",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Validate description when present."""
        return validate_optional_text(
            value,
            field_name="description",
            max_length=255,
        )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        """Validate notes when present."""
        return validate_optional_text(value, field_name="notes", max_length=2000)

    @field_validator("subtotal", "tax_amount", "total_amount")
    @classmethod
    def validate_amounts(cls, value: Decimal) -> Decimal:
        """Validate non-negative expense amount."""
        return validate_non_negative_decimal(value, field_name="amount")

    @field_validator("attachment_count")
    @classmethod
    def validate_attachment_count(cls, value: int) -> int:
        """Validate attachment count."""
        return validate_attachment_count(value)

    @model_validator(mode="after")
    def validate_total_amount(self) -> Self:
        """Validate total amount equals subtotal plus tax."""
        validate_expense_total(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
        )
        return self


class ExpenseUpdate(BaseModel):
    """Request schema for updating an expense."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: uuid.UUID | None = Field(
        default=None,
        description="Updated optional vendor UUID.",
        examples=[str(uuid.uuid4())],
    )
    expense_date: date | None = Field(
        default=None,
        description="Updated expense date.",
        examples=["2026-05-01"],
    )
    category: ExpenseCategory | None = Field(
        default=None,
        description="Updated expense category.",
        examples=[ExpenseCategory.SOFTWARE],
    )
    description: str | None = Field(
        default=None,
        description="Updated expense description.",
        max_length=255,
    )
    subtotal: Decimal | None = Field(default=None, description="Updated subtotal.")
    tax_amount: Decimal | None = Field(default=None, description="Updated tax amount.")
    total_amount: Decimal | None = Field(
        default=None,
        description="Updated total amount.",
    )
    notes: str | None = Field(default=None, description="Updated expense notes.")
    attachment_count: int | None = Field(
        default=None,
        description="Updated attachment count.",
        examples=[1],
    )
    status: ExpenseStatus | None = Field(
        default=None,
        description="Updated expense lifecycle status.",
        examples=[ExpenseStatus.APPROVED],
    )
    lines: list[ExpenseLineUpdate] | None = Field(
        default=None,
        description="Updated expense line items.",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Validate description when present."""
        return validate_optional_text(
            value,
            field_name="description",
            max_length=255,
        )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        """Validate notes when present."""
        return validate_optional_text(value, field_name="notes", max_length=2000)

    @field_validator("subtotal", "tax_amount", "total_amount")
    @classmethod
    def validate_amounts(cls, value: Decimal | None) -> Decimal | None:
        """Validate optional non-negative expense amount."""
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
    def validate_total_amount(self) -> Self:
        """Validate total amount when all amount fields are present."""
        validate_expense_total(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
        )
        return self


class ExpenseListResponse(ExpenseResponseBase):
    """Compact response schema for expense lists."""

    id: uuid.UUID = Field(description="Expense UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    vendor_id: uuid.UUID | None = Field(default=None, description="Vendor UUID.")
    expense_number: str = Field(description="Business-scoped expense number.")
    expense_date: date = Field(description="Expense date.")
    category: ExpenseCategory = Field(description="Expense category.")
    status: ExpenseStatus = Field(description="Expense lifecycle status.")
    total_amount: Decimal = Field(description="Expense total amount.")
    attachment_count: int = Field(description="Expense attachment count.")


class ExpenseResponse(ExpenseListResponse):
    """Response schema for an expense."""

    description: str | None = Field(default=None, description="Expense description.")
    subtotal: Decimal = Field(description="Expense subtotal.")
    tax_amount: Decimal = Field(description="Expense tax amount.")
    notes: str | None = Field(default=None, description="Expense notes.")
    vendor: VendorResponse | None = Field(
        default=None,
        description="Expense vendor.",
    )
    lines: list[ExpenseLineResponse] = Field(
        default_factory=list,
        description="Expense line items.",
    )
