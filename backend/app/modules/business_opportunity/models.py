"""Immutable canonical structures for Business Opportunity v1.0."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.modules.business_forecast.models import (
    ForecastAuthoritativeInput,
    ForecastIdentity,
)


class OpportunityStatus(StrEnum):
    """The complete canonical opportunity-status vocabulary."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNAVAILABLE = "unavailable"


class ConditionStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNAVAILABLE = "unavailable"


class ComparisonOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    IN = "in"


@dataclass(frozen=True, slots=True)
class ConditionInputReference:
    source: str
    capability: str
    field: str
    value_type: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.source, self.capability, self.field, self.value_type)
        ):
            raise ValueError("condition input reference fields must not be blank")
        if self.value_type not in {
            "enum",
            "numeric",
            "text",
            "boolean",
            "date",
            "datetime",
        }:
            raise ValueError("condition input reference value type is not approved")


@dataclass(frozen=True, slots=True)
class ConditionOperand:
    kind: str
    value: Any

    def __post_init__(self) -> None:
        if self.kind not in {"enum", "numeric", "text", "boolean", "date", "datetime"}:
            raise ValueError("condition operand kind is not approved")


@dataclass(frozen=True, slots=True)
class Comparison:
    input_reference: ConditionInputReference
    operator: ComparisonOperator
    operand: ConditionOperand

    def __post_init__(self) -> None:
        if self.input_reference.value_type != self.operand.kind:
            raise ValueError("condition operand kind must match input value type")


@dataclass(frozen=True, slots=True)
class ConditionExpression:
    condition_id: str
    comparison: Comparison | None = None
    all: tuple["ConditionExpression", ...] | None = None
    any: tuple["ConditionExpression", ...] | None = None
    not_: tuple["ConditionExpression", ...] | None = None

    def __post_init__(self) -> None:
        if not self.condition_id.strip():
            raise ValueError("condition identity must not be blank")
        forms = (self.comparison, self.all, self.any, self.not_)
        if sum(item is not None for item in forms) != 1:
            raise ValueError("condition expression requires exactly one form")
        if self.all == () or self.any == ():
            raise ValueError("condition expression groups must not be empty")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("not condition requires exactly one child")


@dataclass(frozen=True, slots=True)
class StatusExpression:
    condition_id: str | None = None
    expected_status: ConditionStatus | None = None
    all: tuple["StatusExpression", ...] | None = None
    any: tuple["StatusExpression", ...] | None = None
    not_: tuple["StatusExpression", ...] | None = None

    def __post_init__(self) -> None:
        reference = self.condition_id is not None or self.expected_status is not None
        forms = (reference, self.all, self.any, self.not_)
        if sum(item is not None for item in forms) != 1:
            raise ValueError("status expression requires exactly one form")
        if reference and (not self.condition_id or self.expected_status is None):
            raise ValueError("status reference requires condition and status")
        if self.all == () or self.any == ():
            raise ValueError("status expression groups must not be empty")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("not status expression requires exactly one child")


@dataclass(frozen=True, slots=True)
class EligibilityResultRule:
    expression: StatusExpression
    result: OpportunityStatus


@dataclass(frozen=True, slots=True)
class EnumVocabulary:
    input_reference: ConditionInputReference
    values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if self.input_reference.value_type != "enum" or not self.values:
            raise ValueError("enum vocabulary requires enum reference and values")
        if len(self.values) != len(set(self.values)):
            raise ValueError("enum vocabulary values must be unique")


@dataclass(frozen=True, slots=True)
class OpportunityPolicy:
    policy_id: str
    version: str
    effective_from: datetime
    effective_until: datetime | None
    conditions: tuple[ConditionExpression, ...]
    result_rules: tuple[EligibilityResultRule, ...]
    provenance: str
    enum_vocabularies: tuple[EnumVocabulary, ...] = ()

    def __post_init__(self) -> None:
        if not all(
            value.strip() for value in (self.policy_id, self.version, self.provenance)
        ):
            raise ValueError(
                "opportunity policy identity and provenance must not be blank"
            )
        if not self.conditions or not self.result_rules:
            raise ValueError("opportunity policy requires conditions and result rules")
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("opportunity policy effective period is invalid")
        condition_ids = tuple(condition.condition_id for condition in self.conditions)
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("opportunity policy condition identities must be unique")


@dataclass(frozen=True, slots=True)
class UnavailableOpportunityInformation:
    source: str
    capability: str
    reference_id: str | None
    field: str
    reason: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.source, self.capability, self.field, self.reason)
        ):
            raise ValueError("unavailable opportunity information must be traceable")


@dataclass(frozen=True, slots=True)
class OpportunityConditionEvaluation:
    condition_id: str
    status: ConditionStatus
    input_reference: ConditionInputReference | None = None
    operator: ComparisonOperator | None = None
    operand: ConditionOperand | None = None
    children: tuple["OpportunityConditionEvaluation", ...] = ()


@dataclass(frozen=True, slots=True)
class OpportunityTraceability:
    source_references: tuple[ForecastAuthoritativeInput, ...]
    evidence: tuple[ForecastAuthoritativeInput, ...]
    input_traceability: tuple[ForecastAuthoritativeInput, ...]
    provenance: str
    temporal_context: datetime
    forecast_identity: ForecastIdentity


@dataclass(frozen=True, slots=True)
class BusinessOpportunity:
    opportunity_id: uuid.UUID
    business_id: uuid.UUID
    status: OpportunityStatus
    assessment_time: datetime
    opportunity_type: str
    canonical_subject: str
    policy_id: str
    policy_version: str
    eligibility_result: OpportunityStatus
    source_references: tuple[ForecastAuthoritativeInput, ...]
    evidence: tuple[ForecastAuthoritativeInput, ...]
    limitations: tuple[str, ...]
    input_traceability: tuple[ForecastAuthoritativeInput, ...]
    provenance: str
    temporal_context: datetime
    condition_evaluations: tuple[OpportunityConditionEvaluation, ...]
    unavailable_information: tuple[UnavailableOpportunityInformation, ...]

    def __post_init__(self) -> None:
        if self.status is not self.eligibility_result:
            raise ValueError("opportunity status must preserve eligibility result")
        if not all(
            value.strip()
            for value in (
                self.opportunity_type,
                self.canonical_subject,
                self.policy_id,
                self.policy_version,
                self.provenance,
            )
        ):
            raise ValueError("opportunity identity and provenance must not be blank")
        if self.temporal_context > self.assessment_time:
            raise ValueError("opportunity temporal context cannot follow assessment")
        if (
            self.status is OpportunityStatus.UNAVAILABLE
            and not self.unavailable_information
        ):
            raise ValueError("unavailable opportunity requires unavailable information")
