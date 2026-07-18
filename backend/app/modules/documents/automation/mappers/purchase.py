"""Purchase automation mapper."""

from decimal import Decimal

from app.modules.documents.automation.mappers.field_map import ExtractedFieldMap
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.purchases.models import PurchaseStatus
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceLineCreate,
)


class PurchaseMapper:
    """Map reviewed extracted fields to a purchase invoice request."""

    def map(self, extracted_document: ExtractedDocument) -> PurchaseInvoiceCreate:
        """Return purchase invoice create request."""
        fields = ExtractedFieldMap(extracted_document)
        return PurchaseInvoiceCreate(
            supplier_id=fields.uuid("supplier_id"),
            invoice_number=fields.required("invoice_number"),
            invoice_date=fields.date("invoice_date"),
            due_date=fields.date("due_date", required=False),
            subtotal=fields.decimal("subtotal"),
            tax_amount=fields.decimal("tax_amount", default=Decimal("0.00")),
            total_amount=fields.decimal("grand_total"),
            notes=fields.first("notes"),
            attachment_count=0,
            status=PurchaseStatus.DRAFT,
            lines=[
                PurchaseInvoiceLineCreate(
                    description=fields.required("line_description"),
                    quantity=fields.decimal("quantity"),
                    unit_cost=fields.decimal("unit_cost"),
                    tax_rate=fields.decimal("tax_rate", default=Decimal("0.00")),
                    line_total=fields.decimal("line_total"),
                )
            ],
        )
