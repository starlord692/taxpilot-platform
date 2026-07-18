"""Regex-based document field extraction."""

import re
from decimal import Decimal

from app.modules.documents.extraction.extractors.types import ExtractedValue
from app.modules.documents.extraction.models import ExtractedFieldSource
from app.modules.documents.models import DocumentType

GSTIN_PATTERN = re.compile(
    r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
    re.IGNORECASE,
)
GSTIN_LABEL_PATTERN = re.compile(r"GSTIN\s*[:\-]?\s*([A-Z0-9]{4,20})", re.IGNORECASE)
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)
INVOICE_NUMBER_PATTERN = re.compile(
    r"(?:invoice\s*(?:no|number|#)\s*[:\-]?\s*)([A-Z0-9\-\/]+)",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(
    r"(subtotal|discount|cgst|sgst|igst|cess|round\s*off|grand\s*total|total)"
    r"\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
PERCENTAGE_PATTERN = re.compile(r"\b([0-9]{1,2}(?:\.\d{1,2})?)\s*%\b")
HSN_PATTERN = re.compile(r"\bHSN\s*[:\-]?\s*([0-9]{4,8})\b", re.IGNORECASE)
SAC_PATTERN = re.compile(r"\bSAC\s*[:\-]?\s*([0-9]{6})\b", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"\b(INR|USD|EUR|GBP)\b|Rs\.", re.IGNORECASE)
PAYMENT_TERMS_PATTERN = re.compile(
    r"(?:payment\s*terms)\s*[:\-]?\s*([A-Za-z0-9 ]{3,80})",
    re.IGNORECASE,
)
NAME_PATTERNS = {
    "supplier_name": re.compile(r"Supplier\s*[:\-]?\s*(.+)", re.IGNORECASE),
    "customer_name": re.compile(r"Customer\s*[:\-]?\s*(.+)", re.IGNORECASE),
}
ADDRESS_PATTERN = re.compile(r"Address\s*[:\-]?\s*(.+)", re.IGNORECASE)
LINE_ITEM_PATTERN = re.compile(
    r"Item\s*[:\-]\s*(?P<description>.+?)\s+Qty\s*[:\-]\s*(?P<quantity>[0-9.]+)"
    r"\s+Unit\s*[:\-]\s*(?P<unit_price>[0-9,.]+)"
    r"(?:\s+Tax\s*[:\-]\s*(?P<tax_rate>[0-9.]+)%?)?"
    r"\s+Total\s*[:\-]\s*(?P<line_total>[0-9,.]+)",
    re.IGNORECASE,
)


class RuleBasedExtractor:
    """Extract common statutory and invoice fields using regex rules."""

    def extract(self, text: str, document_type: DocumentType) -> list[ExtractedValue]:
        """Extract structured fields from OCR text."""
        _ = document_type
        fields: list[ExtractedValue] = []
        fields.extend(self._extract_unique_matches("gstin", GSTIN_PATTERN, text))
        fields.extend(self._extract_invalid_gstin_labels(text, fields))
        fields.extend(self._extract_unique_matches("pan", PAN_PATTERN, text))
        fields.extend(self._extract_dates(text))
        fields.extend(self._extract_invoice_number(text))
        fields.extend(self._extract_amounts(text))
        fields.extend(self._extract_unique_matches("hsn", HSN_PATTERN, text))
        fields.extend(self._extract_unique_matches("sac", SAC_PATTERN, text))
        fields.extend(self._extract_percentages(text))
        fields.extend(self._extract_currency(text))
        fields.extend(self._extract_payment_terms(text))
        fields.extend(self._extract_names(text))
        fields.extend(self._extract_address(text))
        fields.extend(self._extract_line_items(text))
        return fields

    def classify(self, text: str) -> DocumentType:
        """Classify document type from OCR text."""
        normalized = text.lower()
        if "bank statement" in normalized:
            return DocumentType.BANK_STATEMENT
        if "expense" in normalized or "receipt" in normalized:
            return DocumentType.EXPENSE_RECEIPT
        if "purchase invoice" in normalized:
            return DocumentType.PURCHASE_INVOICE
        if "sales invoice" in normalized or "invoice" in normalized:
            return DocumentType.SALES_INVOICE
        if "gst certificate" in normalized or "gstin" in normalized:
            return DocumentType.GST_CERTIFICATE
        return DocumentType.UNKNOWN

    def _extract_unique_matches(
        self,
        field_name: str,
        pattern: re.Pattern[str],
        text: str,
    ) -> list[ExtractedValue]:
        """Extract unique regex matches."""
        values: list[ExtractedValue] = []
        seen: set[str] = set()
        for match in pattern.finditer(text):
            value = (match.group(1) if match.lastindex else match.group(0)).upper()
            if value not in seen:
                values.append(self._field(field_name, value, Decimal("92.00")))
                seen.add(value)
        return values

    def _extract_invalid_gstin_labels(
        self,
        text: str,
        existing_fields: list[ExtractedValue],
    ) -> list[ExtractedValue]:
        """Extract labelled GSTIN values that fail strict GSTIN matching."""
        existing_values = {field.field_value.upper() for field in existing_fields}
        fields: list[ExtractedValue] = []
        for match in GSTIN_LABEL_PATTERN.finditer(text):
            value = match.group(1).upper()
            if value not in existing_values:
                fields.append(self._field("gstin", value, Decimal("55.00")))
                existing_values.add(value)
        return fields

    def _extract_dates(self, text: str) -> list[ExtractedValue]:
        """Extract invoice and due dates."""
        labels = [
            ("invoice_date", re.compile(r"Invoice\s*Date\s*[:\-]?\s*(.+)", re.I)),
            ("due_date", re.compile(r"Due\s*Date\s*[:\-]?\s*(.+)", re.I)),
        ]
        fields: list[ExtractedValue] = []
        for field_name, pattern in labels:
            match = pattern.search(text)
            if match:
                date_match = DATE_PATTERN.search(match.group(1))
                if date_match:
                    fields.append(
                        self._field(field_name, date_match.group(0), Decimal("90.00"))
                    )
        if not fields:
            for match in DATE_PATTERN.finditer(text):
                fields.append(self._field("date", match.group(0), Decimal("82.00")))
        return fields

    def _extract_invoice_number(self, text: str) -> list[ExtractedValue]:
        """Extract invoice number."""
        match = INVOICE_NUMBER_PATTERN.search(text)
        if match is None:
            return []
        return [self._field("invoice_number", match.group(1), Decimal("90.00"))]

    def _extract_amounts(self, text: str) -> list[ExtractedValue]:
        """Extract monetary amounts."""
        field_map = {
            "subtotal": "subtotal",
            "discount": "discount",
            "cgst": "cgst",
            "sgst": "sgst",
            "igst": "igst",
            "cess": "cess",
            "round off": "round_off",
            "grand total": "grand_total",
            "total": "grand_total",
        }
        fields: list[ExtractedValue] = []
        for match in AMOUNT_PATTERN.finditer(text):
            label = re.sub(r"\s+", " ", match.group(1).lower())
            field_name = field_map.get(label, label.replace(" ", "_"))
            fields.append(
                self._field(
                    field_name,
                    match.group(2).replace(",", ""),
                    Decimal("88.00"),
                )
            )
        return fields

    def _extract_percentages(self, text: str) -> list[ExtractedValue]:
        """Extract tax percentages."""
        return [
            self._field("tax_rate", match.group(1), Decimal("82.00"))
            for match in PERCENTAGE_PATTERN.finditer(text)
        ]

    def _extract_currency(self, text: str) -> list[ExtractedValue]:
        """Extract currency."""
        match = CURRENCY_PATTERN.search(text)
        if match is None:
            return []
        value = "INR" if match.group(0).lower().startswith("rs") else match.group(0)
        return [self._field("currency", value, Decimal("85.00"))]

    def _extract_payment_terms(self, text: str) -> list[ExtractedValue]:
        """Extract payment terms."""
        match = PAYMENT_TERMS_PATTERN.search(text)
        if match is None:
            return []
        return [self._field("payment_terms", match.group(1).strip(), Decimal("82.00"))]

    def _extract_names(self, text: str) -> list[ExtractedValue]:
        """Extract supplier and customer names."""
        fields: list[ExtractedValue] = []
        for field_name, pattern in NAME_PATTERNS.items():
            match = pattern.search(text)
            if match:
                fields.append(
                    self._field(field_name, match.group(1).strip(), Decimal("82.00"))
                )
        return fields

    def _extract_address(self, text: str) -> list[ExtractedValue]:
        """Extract address."""
        match = ADDRESS_PATTERN.search(text)
        if match is None:
            return []
        return [self._field("address", match.group(1).strip(), Decimal("78.00"))]

    def _extract_line_items(self, text: str) -> list[ExtractedValue]:
        """Extract simple line item rows as JSON strings."""
        fields: list[ExtractedValue] = []
        for match in LINE_ITEM_PATTERN.finditer(text):
            line_item = {
                "description": match.group("description").strip(),
                "quantity": match.group("quantity"),
                "unit_price": match.group("unit_price").replace(",", ""),
                "tax_rate": match.group("tax_rate") or "",
                "line_total": match.group("line_total").replace(",", ""),
            }
            fields.append(
                self._field("line_items", str(line_item), Decimal("76.00"))
            )
        return fields

    def _field(
        self,
        field_name: str,
        field_value: str,
        confidence: Decimal,
    ) -> ExtractedValue:
        """Build extracted value."""
        return ExtractedValue(
            field_name=field_name,
            field_value=field_value.strip(),
            confidence=confidence,
            source=ExtractedFieldSource.RULE,
        )
