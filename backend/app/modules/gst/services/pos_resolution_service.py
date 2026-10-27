"""Deterministic Supplier Location and Place of Supply Resolution Service under TAX-01.

Implements the 3-step deterministic resolution:
Step 1: Factual evaluation establishing supply category (Cat 1 to 5).
Step 2: Deemed Place of Supply (POS) resolution under statutory provisions:
        - § 10(1)(a): Movement of goods -> destination state.
        - § 10(1)(b): Bill-to/Ship-to tripartite -> buyer's registered principal place of business.
        - § 10(1)(c): Over-the-counter goods without movement -> supplier location.
        - § 12(2)(a): B2B Services -> recipient location.
        - § 12(2)(b)(ii): B2C Services without address -> supplier location.
Step 3: Tax calculation comparison between Supplier Location (L_S) and POS:
        - L_S == POS and POS in UTGST -> INTRA_STATE_UTGST (CGST + UTGST).
        - L_S == POS and POS in SGST  -> INTRA_STATE (CGST + SGST).
        - L_S != POS                  -> INTER_STATE (IGST).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from app.common.exceptions import ValidationException
from app.core.logging import get_logger
from app.modules.gst.evidence import (
    BuyerRegistrationInvalidatedException,
    BuyerRegistrationStaleException,
    BuyerRegistrationUnconfirmedException,
    FreshnessPolicy,
    FreshnessPolicyUndefinedException,
    GSTINVerificationEvidence,
    evaluate_buyer_registration_evidence,
)
from app.modules.gst.jurisdictions import (
    InvalidStateCodeException,
    LegacyStateCodeObsoleteException,
    OffshoreTerritoryUnsupportedException,
    is_utgst_jurisdiction,
    validate_state_code,
)

logger = get_logger(__name__)


class PlaceOfSupplyRequiredException(ValidationException):
    """Raised when place of supply cannot be deterministically resolved."""

    status_code = 422
    error_code = "sales.invoice_place_of_supply_required"


class BillToShipToInvalidException(ValidationException):
    """Raised when bill-to/ship-to tripartite delivery fields are invalid or missing."""

    status_code = 422
    error_code = "sales.invoice_bill_to_ship_to_invalid"


class ConsigneeRequiredException(ValidationException):
    """Raised when bill-to/ship-to supply lacks shipping consignee name."""

    status_code = 422
    error_code = "sales.invoice_consignee_required"


class ShippingStateRequiredException(ValidationException):
    """Raised when shipping state code is missing for physical delivery or bill-to/ship-to."""

    status_code = 422
    error_code = "sales.invoice_shipping_state_required"


class ContradictoryPOSException(ValidationException):
    """Raised when explicit place of supply contradicts statutory determination."""

    status_code = 422
    error_code = "sales.invoice_contradictory_pos"


class TransactionClassificationIndeterminateException(ValidationException):
    """Raised when transaction classification cannot be determined due to missing supplier/entity status."""

    status_code = 422
    error_code = "sales.invoice_transaction_classification_indeterminate"


class DirectionTimingUnestablishedException(ValidationException):
    """Raised when direction timing before/during movement is missing or unestablished."""

    status_code = 422
    error_code = "sales.invoice_direction_timing_unestablished"


class DirectingPartyIndeterminateException(ValidationException):
    """Raised when delivery directing party is an agent or indeterminate third person."""

    status_code = 422
    error_code = "sales.invoice_directing_party_indeterminate"


class SEZUnsupportedException(ValidationException):
    """Raised when supply is made to a Special Economic Zone (SEZ)."""

    status_code = 422
    error_code = "sales.invoice_sez_unsupported"


@dataclass(frozen=True)
class TaxDeterminationErrorContract:
    """Deterministic machine-readable tax error contract definition."""

    error_code: str
    http_status: int
    failure_condition: str
    remediation_guidance: str
    exception_class: type[ValidationException]


TAX_DETERMINATION_ERROR_CATALOG: Final[dict[str, TaxDeterminationErrorContract]] = {
    "sales.invoice_directing_party_indeterminate": TaxDeterminationErrorContract(
        error_code="sales.invoice_directing_party_indeterminate",
        http_status=422,
        failure_condition="Directing party is an agent or third party distinct from billed buyer.",
        remediation_guidance="Agency direction unsupported in Milestone 1; consult tax counsel.",
        exception_class=DirectingPartyIndeterminateException,
    ),
    "sales.invoice_freshness_policy_undefined": TaxDeterminationErrorContract(
        error_code="sales.invoice_freshness_policy_undefined",
        http_status=422,
        failure_condition="Tenant configuration lacks an approved freshness policy.",
        remediation_guidance="Establish approved verification freshness policy.",
        exception_class=FreshnessPolicyUndefinedException,
    ),
    "sales.invoice_buyer_registration_unconfirmed": TaxDeterminationErrorContract(
        error_code="sales.invoice_buyer_registration_unconfirmed",
        http_status=422,
        failure_condition="Buyer has only FORMAT_VALIDATED_UNVERIFIED status or missing evidence.",
        remediation_guidance="Record verified registration evidence from approved source.",
        exception_class=BuyerRegistrationUnconfirmedException,
    ),
    "sales.invoice_buyer_registration_stale": TaxDeterminationErrorContract(
        error_code="sales.invoice_buyer_registration_stale",
        http_status=422,
        failure_condition="Buyer's verification evidence exceeds approved freshness threshold.",
        remediation_guidance="Re-verify buyer registration status to refresh evidence.",
        exception_class=BuyerRegistrationStaleException,
    ),
    "sales.invoice_buyer_registration_invalidated": TaxDeterminationErrorContract(
        error_code="sales.invoice_buyer_registration_invalidated",
        http_status=422,
        failure_condition="Verification invalidated by status change or identity mutation.",
        remediation_guidance="Re-establish verification with updated identity records.",
        exception_class=BuyerRegistrationInvalidatedException,
    ),
    "sales.invoice_direction_timing_unestablished": TaxDeterminationErrorContract(
        error_code="sales.invoice_direction_timing_unestablished",
        http_status=422,
        failure_condition="direction_timing is missing, UNKNOWN, or POST_DELIVERY.",
        remediation_guidance="Attest direction timing as BEFORE_MOVEMENT or DURING_MOVEMENT.",
        exception_class=DirectionTimingUnestablishedException,
    ),
    "sales.invoice_consignee_required": TaxDeterminationErrorContract(
        error_code="sales.invoice_consignee_required",
        http_status=422,
        failure_condition="is_bill_to_ship_to = True passed without consignee name.",
        remediation_guidance="Provide third-party consignee name.",
        exception_class=ConsigneeRequiredException,
    ),
    "sales.invoice_shipping_state_required": TaxDeterminationErrorContract(
        error_code="sales.invoice_shipping_state_required",
        http_status=422,
        failure_condition="Physical delivery or bill-to/ship-to requested without shipping state.",
        remediation_guidance="Provide valid 2-digit shipping_state_code.",
        exception_class=ShippingStateRequiredException,
    ),
    "sales.invoice_place_of_supply_required": TaxDeterminationErrorContract(
        error_code="sales.invoice_place_of_supply_required",
        http_status=422,
        failure_condition="Draft lacks POS and cannot be derived from customer/shipping facts.",
        remediation_guidance="Update draft with explicit POS or structured shipping state.",
        exception_class=PlaceOfSupplyRequiredException,
    ),
    "sales.invoice_contradictory_pos": TaxDeterminationErrorContract(
        error_code="sales.invoice_contradictory_pos",
        http_status=422,
        failure_condition="Explicit POS contradicts physical shipping or customer GSTIN rule.",
        remediation_guidance="Correct contradictory override.",
        exception_class=ContradictoryPOSException,
    ),
    "sales.invoice_offshore_territory_unsupported": TaxDeterminationErrorContract(
        error_code="sales.invoice_offshore_territory_unsupported",
        http_status=422,
        failure_condition="Supply attempted under Code 97 ('Other Territory').",
        remediation_guidance="Offshore operations unsupported in domestic invoicing.",
        exception_class=OffshoreTerritoryUnsupportedException,
    ),
    "sales.invoice_legacy_state_code_obsolete": TaxDeterminationErrorContract(
        error_code="sales.invoice_legacy_state_code_obsolete",
        http_status=422,
        failure_condition="Payload references deprecated state code 25 (Daman & Diu).",
        remediation_guidance="Update state code to canonical merged code 26.",
        exception_class=LegacyStateCodeObsoleteException,
    ),
    # Additional TAX-01 error contracts
    "sales.invoice_sez_unsupported": TaxDeterminationErrorContract(
        error_code="sales.invoice_sez_unsupported",
        http_status=422,
        failure_condition="Supplies to Special Economic Zones (SEZ) under Section 7(5)(b).",
        remediation_guidance="SEZ supplies unsupported in Milestone 1; consult tax counsel.",
        exception_class=SEZUnsupportedException,
    ),
    "sales.invoice_transaction_classification_indeterminate": TaxDeterminationErrorContract(
        error_code="sales.invoice_transaction_classification_indeterminate",
        http_status=422,
        failure_condition="Transaction classification cannot be determined due to missing supplier/entity status.",
        remediation_guidance="Ensure active business registration has valid GSTIN or operating state.",
        exception_class=TransactionClassificationIndeterminateException,
    ),
    "sales.invoice_invalid_state_code": TaxDeterminationErrorContract(
        error_code="sales.invoice_invalid_state_code",
        http_status=422,
        failure_condition="Provided state code is not recognized as a valid Indian GST jurisdiction.",
        remediation_guidance="Provide a valid 2-digit Indian GST state code (01-38).",
        exception_class=InvalidStateCodeException,
    ),
    "sales.invoice_bill_to_ship_to_invalid": TaxDeterminationErrorContract(
        error_code="sales.invoice_bill_to_ship_to_invalid",
        http_status=422,
        failure_condition="Bill-to/ship-to tripartite delivery fields are invalid or missing.",
        remediation_guidance="Provide registered buyer with a valid GSTIN for tripartite supplies.",
        exception_class=BillToShipToInvalidException,
    ),
}


class SupplyCategory(StrEnum):
    """Statutory supply classification categories."""

    CAT_1_B2B_GOODS_MOVEMENT = "CAT_1_B2B_GOODS_MOVEMENT"
    CAT_2_B2B_SERVICES = "CAT_2_B2B_SERVICES"
    CAT_3_B2C_GOODS_DESTINATION = "CAT_3_B2C_GOODS_DESTINATION"
    CAT_4_B2C_OTC = "CAT_4_B2C_OTC"
    CAT_5_B2B_BILL_TO_SHIP_TO = "CAT_5_B2B_BILL_TO_SHIP_TO"


class ResolvedTaxType(StrEnum):
    """Resolved GST tax component combination."""

    INTRA_STATE_SGST = "INTRA_STATE_SGST"  # CGST + SGST
    INTRA_STATE_UTGST = "INTRA_STATE_UTGST"  # CGST + UTGST
    INTER_STATE = "INTER_STATE"  # IGST


class DirectionTiming(StrEnum):
    """Timing of direction for Section 10(1)(b) tripartite supplies."""

    BEFORE_MOVEMENT = "BEFORE_MOVEMENT"
    DURING_MOVEMENT = "DURING_MOVEMENT"


class DirectionEvidenceType(StrEnum):
    """Evidence category for Section 10(1)(b) buyer instructions."""

    PURCHASE_ORDER = "PURCHASE_ORDER"
    WRITTEN_INSTRUCTION = "WRITTEN_INSTRUCTION"
    ELECTRONIC_CONTRACT = "ELECTRONIC_CONTRACT"


@dataclass(frozen=True)
class SupplyResolutionContext:
    """Factual parameters for deterministic supply determination."""

    supplier_state_code: str
    buyer_gstin: str | None = None
    buyer_state_code: str | None = None
    buyer_evidence: GSTINVerificationEvidence | None = None
    freshness_policy: FreshnessPolicy | None = None
    is_service: bool = False
    is_over_the_counter: bool = False
    is_sez: bool = False

    # Tripartite Bill-to / Ship-to fields
    is_bill_to_ship_to: bool = False
    directing_party_is_billed_buyer: bool | None = None
    direction_timing: DirectionTiming | None = None
    direction_evidence_type: DirectionEvidenceType | None = None
    shipping_consignee_name: str | None = None
    shipping_address: str | None = None
    shipping_state_code: str | None = None

    # Asserted overrides and validation flags
    asserted_place_of_supply: str | None = None
    is_delivery_claimed_out_of_state: bool = False

    as_of: datetime | None = None
    environment: str | None = None


@dataclass(frozen=True)
class SupplyResolutionResult:
    """Deterministic place-of-supply resolution output."""

    supplier_state_code: str
    place_of_supply: str
    category: SupplyCategory
    tax_type: ResolvedTaxType
    is_intra_state: bool
    is_utgst: bool
    explanation: str


class PlaceOfSupplyResolutionService:
    """Deterministic server-authoritative Place of Supply and GST classification service."""

    def __init__(self, *, environment: str | None = None) -> None:
        """Initialize POS resolution service with optional environment."""
        self._environment = environment

    def resolve_supply(self, ctx: SupplyResolutionContext) -> SupplyResolutionResult:
        """Resolve POS and tax classification strictly deterministically without AI or live network calls."""
        try:
            return self._resolve_supply_internal(ctx)
        except ValidationException as exc:
            logger.warning(
                "tax_determination_rejected: %s",
                exc.message,
                extra={
                    "reason": exc.error_code,
                    "error_description": exc.message,
                    "details": exc.details,
                    "supplier_state": getattr(ctx, "supplier_state_code", None),
                },
            )
            raise

    def _resolve_supply_internal(
        self, ctx: SupplyResolutionContext
    ) -> SupplyResolutionResult:
        # Validate supplier state
        l_s = validate_state_code(ctx.supplier_state_code)

        if ctx.is_delivery_claimed_out_of_state and not ctx.shipping_state_code:
            raise ShippingStateRequiredException(
                "Delivery to alternate state claimed without shipping_state_code",
                details={"is_delivery_claimed_out_of_state": True},
            )

        if ctx.is_sez:
            raise SEZUnsupportedException(
                "Supplies to Special Economic Zones (SEZ) under Section 7(5)(b) are unsupported in Milestone 1",
                details={"supplier_state": l_s, "is_sez": True},
            )

        # -------------------------------------------------------------
        # STEP 1: FACTUAL CLASSIFICATION
        # -------------------------------------------------------------
        if not ctx.is_bill_to_ship_to:
            if (
                ctx.directing_party_is_billed_buyer is not None
                or ctx.direction_timing is not None
                or ctx.direction_evidence_type is not None
            ):
                raise DirectingPartyIndeterminateException(
                    "Directing party or direction assertions cannot be specified when is_bill_to_ship_to is False",
                    details={
                        "is_bill_to_ship_to": False,
                        "directing_party_is_billed_buyer": ctx.directing_party_is_billed_buyer,
                        "direction_timing": (
                            str(ctx.direction_timing) if ctx.direction_timing else None
                        ),
                    },
                )

        if ctx.is_bill_to_ship_to:
            category = self._validate_and_classify_bill_to_ship_to(ctx, l_s)
            # Step 2 (Deemed POS under Section 10(1)(b)): Billed buyer's registered principal place of business
            buyer_state = self._extract_buyer_state(ctx)
            pos = validate_state_code(buyer_state)
            explanation = (
                f"Tripartite Section 10(1)(b) supply: POS deemed to buyer principal place of business ({pos}), "
                f"delivered to consignee in state ({ctx.shipping_state_code})."
            )

        elif ctx.buyer_gstin is not None and str(ctx.buyer_gstin).strip():
            # Registered Buyer (B2B)
            buyer_state = self._extract_buyer_state(ctx)
            validated_buyer_state = validate_state_code(buyer_state)

            if ctx.is_service:
                # Category 2: B2B Services under Section 12(2)(a)
                category = SupplyCategory.CAT_2_B2B_SERVICES
                pos = validated_buyer_state
                explanation = (
                    f"B2B Services Section 12(2)(a): POS is recipient location ({pos})."
                )
            else:
                # Category 1: B2B Goods with Movement under Section 10(1)(a)
                category = SupplyCategory.CAT_1_B2B_GOODS_MOVEMENT
                if ctx.shipping_state_code and str(ctx.shipping_state_code).strip():
                    pos = validate_state_code(ctx.shipping_state_code)
                else:
                    pos = validated_buyer_state
                explanation = f"B2B Goods Section 10(1)(a): POS is goods movement termination ({pos})."

        # Unregistered Buyer (B2C)
        elif ctx.is_over_the_counter or (
            not ctx.shipping_state_code and not ctx.shipping_address
        ):
            # Category 4: B2C Over-the-Counter Goods (§ 10(1)(c)) or Services without Address (§ 12(2)(b)(ii))
            category = SupplyCategory.CAT_4_B2C_OTC
            pos = l_s
            explanation = f"B2C OTC Section 10(1)(c)/12(2)(b)(ii): POS is supplier location ({pos})."
        elif ctx.shipping_state_code and str(ctx.shipping_state_code).strip():
            # Category 3: B2C Goods with Destination (§ 10(1)(a))
            category = SupplyCategory.CAT_3_B2C_GOODS_DESTINATION
            pos = validate_state_code(ctx.shipping_state_code)
            explanation = (
                f"B2C Goods Section 10(1)(a): POS is delivery destination ({pos})."
            )
        else:
            raise PlaceOfSupplyRequiredException(
                "Unable to resolve Place of Supply: customer has unresolvable delivery address without valid state code",
                details={
                    "supplier_state": l_s,
                    "shipping_address": ctx.shipping_address,
                },
            )

        # Contradictory POS Override Check
        if ctx.asserted_place_of_supply is not None:
            asserted_pos = validate_state_code(ctx.asserted_place_of_supply)
            if asserted_pos != pos:
                raise ContradictoryPOSException(
                    f"Explicit place_of_supply ({asserted_pos}) contradicts determined place of supply ({pos})",
                    details={"asserted": asserted_pos, "resolved": pos},
                )

        # -------------------------------------------------------------
        # STEP 3: TAX CALCULATION COMPARISON (L_S vs POS)
        # -------------------------------------------------------------
        if l_s == pos:
            is_intra_state = True
            if is_utgst_jurisdiction(pos):
                tax_type = ResolvedTaxType.INTRA_STATE_UTGST
                is_utgst = True
            else:
                tax_type = ResolvedTaxType.INTRA_STATE_SGST
                is_utgst = False
        else:
            is_intra_state = False
            tax_type = ResolvedTaxType.INTER_STATE
            is_utgst = False

        result = SupplyResolutionResult(
            supplier_state_code=l_s,
            place_of_supply=pos,
            category=category,
            tax_type=tax_type,
            is_intra_state=is_intra_state,
            is_utgst=is_utgst,
            explanation=explanation,
        )
        logger.info(
            "tax_determination_resolved",
            extra={
                "supplier_state": result.supplier_state_code,
                "place_of_supply": result.place_of_supply,
                "category": result.category.value,
                "tax_type": result.tax_type.value,
                "is_intra_state": result.is_intra_state,
                "is_utgst": result.is_utgst,
                "derivation_basis": result.explanation,
            },
        )
        return result

    def _validate_and_classify_bill_to_ship_to(
        self,
        ctx: SupplyResolutionContext,
        l_s: str,
    ) -> SupplyCategory:
        """Validate Section 10(1)(b) factual prerequisites with fail-closed checks."""
        # 1. Directing party must be the billed buyer (indeterminate facts and agency directions fail closed in Milestone 1)
        if ctx.directing_party_is_billed_buyer is None:
            raise DirectingPartyIndeterminateException(
                "Section 10(1)(b) directing party is unestablished/indeterminate; "
                "directing party must be affirmatively established as the billed buyer",
                details={"directing_party_is_billed_buyer": None},
            )
        if ctx.directing_party_is_billed_buyer is not True:
            raise DirectingPartyIndeterminateException(
                "Section 10(1)(b) agency directions are unsupported in Milestone 1; directing party must be the billed buyer",
                details={
                    "directing_party_is_billed_buyer": ctx.directing_party_is_billed_buyer
                },
            )

        # 2. Buyer must hold verified GSTIN registration
        if not ctx.buyer_gstin or not str(ctx.buyer_gstin).strip():
            raise BillToShipToInvalidException(
                "Bill-to/ship-to tripartite supply requires a registered buyer with a verified GSTIN",
                details={"buyer_gstin": ctx.buyer_gstin},
            )

        # Evaluate evidence lifecycle and freshness policy
        evaluate_buyer_registration_evidence(
            evidence=ctx.buyer_evidence,
            freshness_policy=ctx.freshness_policy,
            as_of=ctx.as_of,
            environment=ctx.environment or self._environment,
        )

        # 3. Delivery destination state and consignee must be present
        if (
            not ctx.shipping_consignee_name
            or not str(ctx.shipping_consignee_name).strip()
        ):
            raise ConsigneeRequiredException(
                "Bill-to/ship-to supply requires a non-empty shipping consignee name",
                details={"shipping_consignee_name": ctx.shipping_consignee_name},
            )

        if not ctx.shipping_state_code or not str(ctx.shipping_state_code).strip():
            raise ShippingStateRequiredException(
                "Bill-to/ship-to supply requires a valid shipping destination state code",
                details={"shipping_state_code": ctx.shipping_state_code},
            )
        validate_state_code(ctx.shipping_state_code)

        # 4. Direction timing must be established before or during movement
        if ctx.direction_timing not in (
            DirectionTiming.BEFORE_MOVEMENT,
            DirectionTiming.DURING_MOVEMENT,
        ):
            raise DirectionTimingUnestablishedException(
                "Section 10(1)(b) direction timing must be established as BEFORE_MOVEMENT or DURING_MOVEMENT",
                details={"direction_timing": str(ctx.direction_timing)},
            )

        return SupplyCategory.CAT_5_B2B_BILL_TO_SHIP_TO

    def _extract_buyer_state(self, ctx: SupplyResolutionContext) -> str:
        """Extract and validate buyer state code from context or GSTIN prefix."""
        if ctx.buyer_state_code and str(ctx.buyer_state_code).strip():
            return ctx.buyer_state_code.strip()
        if ctx.buyer_gstin and len(str(ctx.buyer_gstin).strip()) >= 2:
            return str(ctx.buyer_gstin).strip()[:2]
        raise PlaceOfSupplyRequiredException(
            "Buyer state code could not be extracted from buyer registration or context",
            details={
                "buyer_gstin": ctx.buyer_gstin,
                "buyer_state_code": ctx.buyer_state_code,
            },
        )
