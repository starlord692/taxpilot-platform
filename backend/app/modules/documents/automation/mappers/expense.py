"""Expense automation mapper."""

from decimal import Decimal

from app.modules.documents.automation.mappers.field_map import ExtractedFieldMap
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.expenses.models import ExpenseCategory, ExpenseStatus
from app.modules.expenses.schemas import ExpenseCreate, ExpenseLineCreate


class ExpenseMapper:
    """Map reviewed extracted fields to an expense request."""

    def map(self, extracted_document: ExtractedDocument) -> ExpenseCreate:
        """Return expense create request."""
        fields = ExtractedFieldMap(extracted_document)
        category_value = fields.first("expense_category") or ExpenseCategory.OTHER.value
        return ExpenseCreate(
            vendor_id=fields.uuid("vendor_id", required=False),
            expense_date=fields.date("expense_date")
            or fields.date("invoice_date"),
            category=ExpenseCategory(category_value),
            description=fields.first("description"),
            subtotal=fields.decimal("subtotal"),
            tax_amount=fields.decimal("tax_amount", default=Decimal("0.00")),
            total_amount=fields.decimal("grand_total"),
            notes=fields.first("notes"),
            attachment_count=0,
            status=ExpenseStatus.DRAFT,
            lines=[
                ExpenseLineCreate(
                    description=fields.required("line_description"),
                    quantity=fields.decimal("quantity"),
                    unit_cost=fields.decimal("unit_cost"),
                    tax_rate=fields.decimal("tax_rate", default=Decimal("0.00")),
                    line_total=fields.decimal("line_total"),
                )
            ],
        )
