"""Reusable GST calculation engine."""

import uuid
from collections.abc import Iterable
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.events import EventDispatcher
from app.modules.gst.events import GSTCalculatedEvent, GSTRecalculatedEvent
from app.modules.gst.models import GSTRoundingMethod, GSTSettings

MONEY_PLACES = Decimal("0.01")
TAX_DIVISOR = Decimal("100.00")
ZERO_AMOUNT = Decimal("0.00")


class GSTSupplyType(StrEnum):
    """Supported GST supply scenarios."""

    INTRA_STATE = "intra_state"
    INTER_STATE = "inter_state"
    ZERO_RATED = "zero_rated"
    EXEMPT = "exempt"
    NIL_RATED = "nil_rated"


class GSTCalculationLineInput(BaseModel):
    """Input contract for one GST-calculated line."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="Line item")
    quantity: Decimal
    unit_amount: Decimal
    discount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Decimal("0.00")
    cess_rate: Decimal = Decimal("0.00")
    supply_type: GSTSupplyType = GSTSupplyType.INTRA_STATE
    reverse_charge: bool = False
    composition_dealer: bool = False
    hsn_code: str | None = None
    sac_code: str | None = None

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        """Validate positive quantity."""
        if value <= ZERO_AMOUNT:
            raise ValueError("quantity must be greater than zero")
        return value

    @field_validator("unit_amount", "discount", "tax_rate", "cess_rate")
    @classmethod
    def validate_non_negative(cls, value: Decimal) -> Decimal:
        """Validate non-negative decimal inputs."""
        if value < ZERO_AMOUNT:
            raise ValueError("GST calculation values cannot be negative")
        return value


class GSTCalculationRequest(BaseModel):
    """Input contract for invoice, purchase, or expense GST calculation."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    business_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None = None
    lines: list[GSTCalculationLineInput]
    tax_inclusive: bool = False
    rounding_method: GSTRoundingMethod = GSTRoundingMethod.NEAREST
    seller_state_code: str | None = None
    buyer_state_code: str | None = None
    place_of_supply: str | None = None
    seller_registration: Any | None = None
    buyer_registration: Any | None = None
    gst_settings: GSTSettings | None = None
    is_recalculation: bool = False

    @field_validator("lines")
    @classmethod
    def validate_lines(
        cls,
        value: list[GSTCalculationLineInput],
    ) -> list[GSTCalculationLineInput]:
        """Validate at least one line is present."""
        if not value:
            raise ValueError("GST calculation requires at least one line")
        return value


class GSTLineBreakdown(BaseModel):
    """GST breakdown for one line."""

    model_config = ConfigDict(frozen=True)

    description: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    tax_amount: Decimal
    effective_tax_rate: Decimal
    line_total: Decimal
    supply_type: GSTSupplyType
    reverse_charge: bool
    input_tax_credit_available: bool


class GSTBreakdown(BaseModel):
    """GST breakdown for an invoice, purchase, or expense."""

    model_config = ConfigDict(frozen=True)

    business_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID | None
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    lines: list[GSTLineBreakdown]


class GSTCalculationService:
    """Central GST calculation engine."""

    def __init__(self, event_dispatcher: EventDispatcher | None = None) -> None:
        """Initialize with an optional event dispatcher."""
        self._event_dispatcher = event_dispatcher

    async def calculate_invoice(
        self,
        request: GSTCalculationRequest,
    ) -> GSTBreakdown:
        """Calculate GST for a sales invoice."""
        return await self.calculate_tax_breakdown(request)

    async def calculate_purchase(
        self,
        request: GSTCalculationRequest,
    ) -> GSTBreakdown:
        """Calculate GST for a purchase invoice."""
        return await self.calculate_tax_breakdown(request)

    async def calculate_expense(
        self,
        request: GSTCalculationRequest,
    ) -> GSTBreakdown:
        """Calculate GST for an expense."""
        return await self.calculate_tax_breakdown(request)

    async def calculate_tax_breakdown(
        self,
        request: GSTCalculationRequest,
    ) -> GSTBreakdown:
        """Calculate GST totals for multiple lines."""
        validated = self._prepare_request(request)
        lines = [
            self.calculate_line(
                line,
                tax_inclusive=validated.tax_inclusive,
                rounding_method=validated.rounding_method,
                default_supply_type=self._derive_supply_type(validated),
            )
            for line in validated.lines
        ]
        breakdown = GSTBreakdown(
            business_id=validated.business_id,
            source_type=validated.source_type,
            source_id=validated.source_id,
            taxable_value=self._sum_money(line.taxable_value for line in lines),
            cgst_amount=self._sum_money(line.cgst_amount for line in lines),
            sgst_amount=self._sum_money(line.sgst_amount for line in lines),
            igst_amount=self._sum_money(line.igst_amount for line in lines),
            cess_amount=self._sum_money(line.cess_amount for line in lines),
            tax_amount=self._sum_money(line.tax_amount for line in lines),
            total_amount=self._sum_money(line.line_total for line in lines),
            lines=lines,
        )
        await self._publish_event(validated)
        return breakdown

    def calculate_line(
        self,
        line: GSTCalculationLineInput,
        *,
        tax_inclusive: bool = False,
        rounding_method: GSTRoundingMethod = GSTRoundingMethod.NEAREST,
        default_supply_type: GSTSupplyType = GSTSupplyType.INTRA_STATE,
    ) -> GSTLineBreakdown:
        """Calculate GST for one line."""
        validated = GSTCalculationLineInput.model_validate(line)
        supply_type = validated.supply_type or default_supply_type
        rate = self._effective_rate(validated)
        gross_amount = validated.quantity * validated.unit_amount
        amount_after_discount = max(gross_amount - validated.discount, ZERO_AMOUNT)
        taxable_value = self._taxable_value(
            amount_after_discount,
            rate=rate,
            cess_rate=validated.cess_rate,
            tax_inclusive=tax_inclusive,
            rounding_method=rounding_method,
        )
        component_total = self._round(
            taxable_value * rate / TAX_DIVISOR,
            rounding_method,
        )
        cess_amount = self._round(
            taxable_value * validated.cess_rate / TAX_DIVISOR,
            rounding_method,
        )
        cgst_amount = ZERO_AMOUNT
        sgst_amount = ZERO_AMOUNT
        igst_amount = ZERO_AMOUNT
        if supply_type == GSTSupplyType.INTRA_STATE and component_total > ZERO_AMOUNT:
            cgst_amount = self._round(component_total / Decimal("2"), rounding_method)
            sgst_amount = self._round(component_total - cgst_amount, rounding_method)
        elif supply_type == GSTSupplyType.INTER_STATE:
            igst_amount = component_total

        tax_amount = self._round(
            cgst_amount + sgst_amount + igst_amount + cess_amount,
            rounding_method,
        )
        line_total = (
            amount_after_discount
            if tax_inclusive
            else self._round(taxable_value + tax_amount, rounding_method)
        )
        return GSTLineBreakdown(
            description=validated.description,
            taxable_value=taxable_value,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            igst_amount=igst_amount,
            cess_amount=cess_amount,
            tax_amount=tax_amount,
            effective_tax_rate=rate + validated.cess_rate,
            line_total=line_total,
            supply_type=supply_type,
            reverse_charge=validated.reverse_charge,
            input_tax_credit_available=not (
                validated.reverse_charge or validated.composition_dealer
            ),
        )

    def _prepare_request(self, request: GSTCalculationRequest) -> GSTCalculationRequest:
        """Apply settings and validate registrations before calculation."""
        validated = GSTCalculationRequest.model_validate(request)
        self._validate_registration(validated.seller_registration, "seller")
        self._validate_registration(validated.buyer_registration, "buyer")
        if validated.gst_settings is None:
            return validated
        return validated.model_copy(
            update={
                "tax_inclusive": validated.gst_settings.tax_inclusive,
                "rounding_method": validated.gst_settings.rounding_method,
            }
        )

    def _derive_supply_type(self, request: GSTCalculationRequest) -> GSTSupplyType:
        """Infer intra/inter-state supply when place information is available."""
        if request.place_of_supply is None or request.seller_state_code is None:
            return GSTSupplyType.INTRA_STATE
        if request.place_of_supply == request.seller_state_code:
            return GSTSupplyType.INTRA_STATE
        return GSTSupplyType.INTER_STATE

    def _effective_rate(self, line: GSTCalculationLineInput) -> Decimal:
        """Return effective GST rate for a line scenario."""
        if line.supply_type in {
            GSTSupplyType.ZERO_RATED,
            GSTSupplyType.EXEMPT,
            GSTSupplyType.NIL_RATED,
        }:
            return ZERO_AMOUNT
        if line.composition_dealer:
            return ZERO_AMOUNT
        return line.tax_rate

    def _taxable_value(
        self,
        amount: Decimal,
        *,
        rate: Decimal,
        cess_rate: Decimal,
        tax_inclusive: bool,
        rounding_method: GSTRoundingMethod,
    ) -> Decimal:
        """Return taxable value for inclusive or exclusive pricing."""
        if not tax_inclusive:
            return self._round(amount, rounding_method)
        divisor = Decimal("1") + ((rate + cess_rate) / TAX_DIVISOR)
        if divisor == Decimal("1"):
            return self._round(amount, rounding_method)
        return self._round(amount / divisor, rounding_method)

    def _round(
        self,
        value: Decimal,
        rounding_method: GSTRoundingMethod,
    ) -> Decimal:
        """Round money according to GST settings."""
        rounding = {
            GSTRoundingMethod.NEAREST: ROUND_HALF_UP,
            GSTRoundingMethod.UP: ROUND_CEILING,
            GSTRoundingMethod.DOWN: ROUND_FLOOR,
        }[rounding_method]
        return value.quantize(MONEY_PLACES, rounding=rounding)

    def _sum_money(self, values: Iterable[Decimal]) -> Decimal:
        """Sum monetary values with two-decimal precision."""
        return sum(values, ZERO_AMOUNT).quantize(MONEY_PLACES)

    def _validate_registration(self, registration: Any | None, label: str) -> None:
        """Validate an optional GST registration object."""
        if registration is None:
            return
        if not getattr(registration, "is_active", False):
            raise ValueError(f"{label} GST registration must be active")

    async def _publish_event(self, request: GSTCalculationRequest) -> None:
        """Publish calculation lifecycle event when a dispatcher is configured."""
        if self._event_dispatcher is None:
            return
        event_cls = (
            GSTRecalculatedEvent
            if request.is_recalculation
            else GSTCalculatedEvent
        )
        await self._event_dispatcher.dispatch(
            event_cls(
                business_id=request.business_id,
                source_type=request.source_type,
                source_id=request.source_id,
            )
        )
