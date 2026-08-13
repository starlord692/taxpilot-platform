"""Immutable canonical structures for Business Risk v1.0."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.modules.business_forecast.models import ForecastIdentity


class RiskCategory(StrEnum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    CUSTOMER = "customer"
    MARKET = "market"
    LIQUIDITY = "liquidity"
    GROWTH = "growth"
    STRATEGIC = "strategic"


class RiskStatus(StrEnum):
    IDENTIFIED = "identified"
    NOT_IDENTIFIED = "not_identified"
    UNAVAILABLE = "unavailable"


class RiskSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ApplicabilityOutcome(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class ConditionStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNAVAILABLE = "unavailable"


class ConditionKind(StrEnum):
    COMPARISON = "comparison"
    ALL = "all"
    ANY = "any"
    NOT = "not"


class ComparisonOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"


@dataclass(frozen=True, slots=True)
class RiskInputReference:
    source: str
    capability: str
    field: str
    value_type: str

    def __post_init__(self) -> None:
        if not all(
            v.strip()
            for v in (self.source, self.capability, self.field, self.value_type)
        ):
            raise ValueError("risk input reference fields must not be blank")
        if self.value_type not in {
            "numeric",
            "text",
            "boolean",
            "date",
            "datetime",
            "enum",
        }:
            raise ValueError("risk input reference value type is not approved")


@dataclass(frozen=True, slots=True)
class RiskConditionExpression:
    condition_id: str
    input_reference: RiskInputReference | None = None
    operator: ComparisonOperator | None = None
    operand: Any | None = None
    all: tuple["RiskConditionExpression", ...] | None = None
    any: tuple["RiskConditionExpression", ...] | None = None
    not_: tuple["RiskConditionExpression", ...] | None = None

    def __post_init__(self) -> None:
        comparison = (
            self.input_reference is not None
            or self.operator is not None
            or self.operand is not None
        )
        choices = (
            comparison,
            self.all is not None,
            self.any is not None,
            self.not_ is not None,
        )
        if not self.condition_id.strip() or sum(choices) != 1:
            raise ValueError("risk condition requires exactly one form")
        if comparison and (self.input_reference is None or self.operator is None):
            raise ValueError("comparison requires fields")
        if self.all == () or self.any == ():
            raise ValueError("all and any require children")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("not requires exactly one child")


@dataclass(frozen=True, slots=True)
class RiskApplicability:
    expression: RiskConditionExpression | None = None


@dataclass(frozen=True, slots=True)
class RiskRule:
    risk_rule_id: str
    category: RiskCategory
    severity: RiskSeverity
    applicability: RiskApplicability
    condition: RiskConditionExpression
    provenance: str


@dataclass(frozen=True, slots=True)
class RiskAssessmentPolicy:
    policy_id: str
    version: str
    effective_from: datetime
    effective_until: datetime | None
    applicability: RiskApplicability
    risk_rules: tuple[RiskRule, ...]
    provenance: str

    def __post_init__(self) -> None:
        if not self.risk_rules or not all(
            v.strip() for v in (self.policy_id, self.version, self.provenance)
        ):
            raise ValueError("risk policy is incomplete")
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("risk policy effective period is invalid")
        if len({r.risk_rule_id for r in self.risk_rules}) != len(self.risk_rules):
            raise ValueError("risk rules must be unique")


@dataclass(frozen=True, slots=True)
class RiskConditionEvaluation:
    kind: ConditionKind
    status: ConditionStatus
    condition_id: str
    input_reference: RiskInputReference | None = None
    operator: ComparisonOperator | None = None
    operand: Any | None = None
    children: tuple["RiskConditionEvaluation", ...] = ()

    def __post_init__(self) -> None:
        if self.kind is ConditionKind.COMPARISON:
            if (
                self.input_reference is None
                or self.operator is None
                or self.operand is None
                or self.children
            ):
                raise ValueError("comparison evaluation requires comparison details")
        elif self.input_reference is not None or self.operator is not None:
            raise ValueError("composite evaluation cannot contain comparison details")


@dataclass(frozen=True, slots=True)
class RiskEvidenceReference:
    source: str
    capability: str
    reference_id: str
    field: str


@dataclass(frozen=True, slots=True)
class UnavailableRiskInformation:
    """Supplementary immutable detail for unavailable authoritative information."""

    condition_id: str
    input_reference: RiskInputReference | None
    condition_status: ConditionStatus
    limitation: str

    def __post_init__(self) -> None:
        if self.condition_status is not ConditionStatus.UNAVAILABLE:
            raise ValueError("unavailable risk information requires unavailable status")
        if not self.condition_id.strip() or not self.limitation.strip():
            raise ValueError("unavailable risk information must be traceable")


@dataclass(frozen=True, slots=True)
class RiskTraceability:
    evaluation_id: str
    forecast_identity: ForecastIdentity
    policy_id: str
    policy_version: str
    risk_rule_id: str
    evidence: tuple[RiskEvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class BusinessRisk:
    risk_id: uuid.UUID
    business_id: uuid.UUID
    forecast_identity: ForecastIdentity
    policy_id: str
    policy_version: str
    risk_rule_id: str
    evaluated_at: datetime
    status: RiskStatus
    category: RiskCategory | None
    severity: RiskSeverity | None
    condition_evaluation: RiskConditionEvaluation
    evidence: tuple[RiskEvidenceReference, ...]
    limitations: tuple[str, ...]
    traceability: RiskTraceability
    unavailable_information: tuple[UnavailableRiskInformation, ...] = ()

    def __post_init__(self) -> None:
        if (self.status is RiskStatus.IDENTIFIED) != (
            self.category is not None and self.severity is not None
        ):
            raise ValueError("category and severity must match identified status")


@dataclass(frozen=True, slots=True)
class RiskEvaluationContext:
    evaluation_id: str
    business_id: uuid.UUID
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class RiskEvaluationResult:
    """Immutable evaluation boundary; does not aggregate independent Risks."""

    policy_applicability: ApplicabilityOutcome
    policy_condition_evaluation: RiskConditionEvaluation | None
    risks: tuple[BusinessRisk, ...]
    limitations: tuple[str, ...]
    unavailable_information: tuple[UnavailableRiskInformation, ...]
