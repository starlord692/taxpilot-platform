"""Business validators for extracted documents."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.review.models import (
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    re.IGNORECASE,
)
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.IGNORECASE)
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y")
SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}


class MasterDataLookup(Protocol):
    """Lookup contract used by matching validators."""

    async def customer_exists(self, business_id: uuid.UUID, name: str) -> bool:
        """Return whether matching customer exists."""
        ...

    async def vendor_exists(self, business_id: uuid.UUID, name: str) -> bool:
        """Return whether matching vendor exists."""
        ...

    async def product_exists(self, business_id: uuid.UUID, description: str) -> bool:
        """Return whether matching product exists."""
        ...

    async def hsn_exists(self, code: str) -> bool:
        """Return whether HSN exists."""
        ...

    async def sac_exists(self, code: str) -> bool:
        """Return whether SAC exists."""
        ...

    async def gst_registration_exists(self, gstin: str) -> bool:
        """Return whether GSTIN exists in registration master."""
        ...

    async def sales_invoice_exists(
        self,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> bool:
        """Return whether sales invoice number exists."""
        ...

    async def purchase_invoice_exists(
        self,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> bool:
        """Return whether purchase invoice number exists."""
        ...


@dataclass(frozen=True)
class ExtractedFieldMap:
    """Lookup wrapper around extracted fields."""

    values: dict[str, list[str]]

    @classmethod
    def from_document(
        cls,
        extracted_document: ExtractedDocument,
    ) -> "ExtractedFieldMap":
        """Build field map from extracted document."""
        values: dict[str, list[str]] = {}
        for field in extracted_document.fields:
            values.setdefault(field.field_name, []).append(field.field_value)
        return cls(values=values)

    def first(self, field_name: str) -> str | None:
        """Return first field value."""
        values = self.values.get(field_name, [])
        return values[0] if values else None

    def all(self, field_name: str) -> list[str]:
        """Return all field values."""
        return self.values.get(field_name, [])


class BusinessValidationPipeline:
    """Run business validators for extracted documents."""

    async def validate(
        self,
        extracted_document: ExtractedDocument,
        lookup: MasterDataLookup,
    ) -> list[ValidationIssue]:
        """Return validation issues for an extracted document."""
        fields = ExtractedFieldMap.from_document(extracted_document)
        issues: list[ValidationIssue] = []
        issues.extend(self._validate_gstin(extracted_document, fields))
        issues.extend(self._validate_pan(extracted_document, fields))
        issues.extend(self._validate_dates(extracted_document, fields))
        issues.extend(self._validate_currency(extracted_document, fields))
        issues.extend(self._validate_mandatory(extracted_document, fields))
        issues.extend(self._validate_totals(extracted_document, fields))
        issues.extend(self._validate_tax_consistency(extracted_document, fields))
        issues.extend(
            await self._validate_duplicates(extracted_document, fields, lookup)
        )
        issues.extend(
            await self._validate_master_data(extracted_document, fields, lookup)
        )
        return issues

    def _validate_gstin(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate GSTIN fields."""
        issues: list[ValidationIssue] = []
        for field_name in ("gstin", "supplier_gstin", "customer_gstin"):
            for value in fields.all(field_name):
                if not GSTIN_PATTERN.fullmatch(value):
                    issues.append(
                        self._issue(
                            extracted_document,
                            ValidationSeverity.ERROR,
                            ValidationCategory.GST,
                            field_name,
                            "Invalid GSTIN format",
                            "Valid Indian GSTIN",
                            value,
                        )
                    )
        return issues

    def _validate_pan(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate PAN fields."""
        pan = fields.first("pan")
        if pan is None or PAN_PATTERN.fullmatch(pan):
            return []
        return [
            self._issue(
                extracted_document,
                ValidationSeverity.ERROR,
                ValidationCategory.PAN,
                "pan",
                "Invalid PAN format",
                "Valid Indian PAN",
                pan,
            )
        ]

    def _validate_dates(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate date fields."""
        issues: list[ValidationIssue] = []
        for field_name in ("invoice_date", "due_date"):
            value = fields.first(field_name)
            if value is not None and self._parse_date(value) is None:
                issues.append(
                    self._issue(
                        extracted_document,
                        ValidationSeverity.ERROR,
                        ValidationCategory.DATE,
                        field_name,
                        "Invalid date format",
                        "DD/MM/YYYY or YYYY-MM-DD",
                        value,
                    )
                )
        return issues

    def _validate_currency(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate currency."""
        currency = fields.first("currency")
        if currency is None or currency.upper() in SUPPORTED_CURRENCIES:
            return []
        return [
            self._issue(
                extracted_document,
                ValidationSeverity.WARNING,
                ValidationCategory.CURRENCY,
                "currency",
                "Unsupported currency",
                ",".join(sorted(SUPPORTED_CURRENCIES)),
                currency,
            )
        ]

    def _validate_mandatory(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate mandatory fields."""
        issues: list[ValidationIssue] = []
        for field_name in ("invoice_number", "grand_total"):
            if fields.first(field_name) is None:
                issues.append(
                    self._issue(
                        extracted_document,
                        ValidationSeverity.ERROR,
                        ValidationCategory.MANDATORY,
                        field_name,
                        "Mandatory field is missing",
                        field_name,
                        None,
                    )
                )
        return issues

    def _validate_totals(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate invoice totals."""
        subtotal = self._decimal(fields.first("subtotal"))
        discount = self._decimal(fields.first("discount")) or Decimal("0.00")
        cgst = self._decimal(fields.first("cgst")) or Decimal("0.00")
        sgst = self._decimal(fields.first("sgst")) or Decimal("0.00")
        igst = self._decimal(fields.first("igst")) or Decimal("0.00")
        cess = self._decimal(fields.first("cess")) or Decimal("0.00")
        round_off = self._decimal(fields.first("round_off")) or Decimal("0.00")
        grand_total = self._decimal(fields.first("grand_total"))
        if subtotal is None or grand_total is None:
            return []
        expected = subtotal - discount + cgst + sgst + igst + cess + round_off
        if abs(expected - grand_total) <= Decimal("1.00"):
            return []
        return [
            self._issue(
                extracted_document,
                ValidationSeverity.ERROR,
                ValidationCategory.TOTAL,
                "grand_total",
                "Grand total does not match subtotal and tax values",
                str(expected),
                str(grand_total),
            )
        ]

    def _validate_tax_consistency(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
    ) -> list[ValidationIssue]:
        """Validate tax consistency."""
        tax_components = [
            self._decimal(fields.first(field_name)) or Decimal("0.00")
            for field_name in ("cgst", "sgst", "igst", "cess")
        ]
        tax_amount = self._decimal(fields.first("tax_amount"))
        if tax_amount is None:
            return []
        actual = sum(tax_components)
        if abs(actual - tax_amount) <= Decimal("1.00"):
            return []
        return [
            self._issue(
                extracted_document,
                ValidationSeverity.ERROR,
                ValidationCategory.TAX,
                "tax_amount",
                "Tax amount does not match GST components",
                str(actual),
                str(tax_amount),
            )
        ]

    async def _validate_duplicates(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
        lookup: MasterDataLookup,
    ) -> list[ValidationIssue]:
        """Validate duplicate invoice number."""
        invoice_number = fields.first("invoice_number")
        if invoice_number is None:
            return []
        exists = await lookup.sales_invoice_exists(
            extracted_document.business_id,
            invoice_number,
        ) or await lookup.purchase_invoice_exists(
            extracted_document.business_id,
            invoice_number,
        )
        if not exists:
            return []
        return [
            self._issue(
                extracted_document,
                ValidationSeverity.ERROR,
                ValidationCategory.DUPLICATE,
                "invoice_number",
                "Duplicate invoice number exists",
                "Unique invoice number",
                invoice_number,
            )
        ]

    async def _validate_master_data(
        self,
        extracted_document: ExtractedDocument,
        fields: ExtractedFieldMap,
        lookup: MasterDataLookup,
    ) -> list[ValidationIssue]:
        """Validate master-data matches."""
        issues: list[ValidationIssue] = []
        customer_name = fields.first("customer_name")
        if customer_name and not await lookup.customer_exists(
            extracted_document.business_id,
            customer_name,
        ):
            issues.append(
                self._matching_issue(extracted_document, "customer_name", customer_name)
            )
        vendor_name = fields.first("supplier_name")
        if vendor_name and not await lookup.vendor_exists(
            extracted_document.business_id,
            vendor_name,
        ):
            issues.append(
                self._matching_issue(extracted_document, "supplier_name", vendor_name)
            )
        for line_item in fields.all("line_items"):
            if not await lookup.product_exists(
                extracted_document.business_id,
                line_item,
            ):
                issues.append(
                    self._matching_issue(extracted_document, "line_items", line_item)
                )
        for hsn in fields.all("hsn"):
            if not await lookup.hsn_exists(hsn):
                issues.append(self._matching_issue(extracted_document, "hsn", hsn))
        for sac in fields.all("sac"):
            if not await lookup.sac_exists(sac):
                issues.append(self._matching_issue(extracted_document, "sac", sac))
        for gstin in fields.all("gstin"):
            if not await lookup.gst_registration_exists(gstin):
                issues.append(self._matching_issue(extracted_document, "gstin", gstin))
        return issues

    def _matching_issue(
        self,
        extracted_document: ExtractedDocument,
        field_name: str,
        actual_value: str,
    ) -> ValidationIssue:
        """Create master-data matching warning."""
        return self._issue(
            extracted_document,
            ValidationSeverity.WARNING,
            ValidationCategory.MATCHING,
            field_name,
            "No matching master-data record found",
            "Existing master-data record",
            actual_value,
        )

    def _issue(
        self,
        extracted_document: ExtractedDocument,
        severity: ValidationSeverity,
        category: ValidationCategory,
        field_name: str,
        message: str,
        expected_value: str | None,
        actual_value: str | None,
    ) -> ValidationIssue:
        """Build validation issue."""
        return ValidationIssue(
            document_id=extracted_document.document_id,
            severity=severity,
            category=category,
            field_name=field_name,
            message=message,
            expected_value=expected_value,
            actual_value=actual_value,
            resolved=False,
        )

    def _decimal(self, value: str | None) -> Decimal | None:
        """Parse decimal."""
        if value is None:
            return None
        try:
            return Decimal(value)
        except ValueError:
            return None

    def _parse_date(self, value: str) -> object | None:
        """Parse supported date formats."""
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None
