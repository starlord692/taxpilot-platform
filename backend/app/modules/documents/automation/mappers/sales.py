"""Sales automation mapper."""

from decimal import Decimal

from app.modules.documents.automation.mappers.field_map import ExtractedFieldMap
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.sales.models import InvoiceStatus
from app.modules.sales.schemas import InvoiceCreateRequest, InvoiceLineRequest


class SalesMapper:
    """Map reviewed extracted fields to a sales invoice request."""

    def map(self, extracted_document: ExtractedDocument) -> InvoiceCreateRequest:
        """Return sales invoice create request."""
        fields = ExtractedFieldMap(extracted_document)
        description = fields.required("line_description")
        quantity = fields.decimal("quantity")
        unit_price = fields.decimal("unit_price")
        tax_rate = fields.decimal("tax_rate", default=Decimal("0.00"))
        discount = fields.decimal("discount", default=Decimal("0.00"))
        line_total = fields.decimal("line_total")
        subtotal = fields.decimal("subtotal")
        tax_amount = fields.decimal("tax_amount", default=Decimal("0.00"))
        total_amount = fields.decimal("grand_total")
        return InvoiceCreateRequest(
            business_id=extracted_document.business_id,
            customer_id=fields.uuid("customer_id"),
            invoice_number=fields.required("invoice_number"),
            invoice_date=fields.date("invoice_date"),
            due_date=fields.date("due_date", required=False),
            status=InvoiceStatus.DRAFT,
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=subtotal - discount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            notes=fields.first("notes"),
            lines=[
                InvoiceLineRequest(
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount=discount,
                    tax_rate=tax_rate,
                    line_total=line_total,
                )
            ],
        )
