"""Reusable catalog tax classification value object."""

from dataclasses import dataclass
from decimal import Decimal

from app.modules.catalog.models.enums import ItemType

MAX_TAX_RATE = Decimal("100.00")


@dataclass(frozen=True, slots=True)
class TaxClassification:
    hsn_code: str | None = None
    sac_code: str | None = None
    gst_rate: Decimal = Decimal("0.00")
    cess_rate: Decimal = Decimal("0.00")

    def validate_for(self, item_type: ItemType) -> None:
        if self.hsn_code and self.sac_code:
            raise ValueError("tax classification cannot contain both HSN and SAC")
        if item_type is ItemType.PRODUCT and self.sac_code:
            raise ValueError("product catalog items cannot use SAC classification")
        if item_type is ItemType.SERVICE and self.hsn_code:
            raise ValueError("service catalog items cannot use HSN classification")
        for name, value in (("gst_rate", self.gst_rate), ("cess_rate", self.cess_rate)):
            if value < 0 or value > MAX_TAX_RATE:
                raise ValueError(f"{name} must be between 0 and 100")
