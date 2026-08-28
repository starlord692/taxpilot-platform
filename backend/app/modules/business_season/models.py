"""Immutable canonical structures for deterministic Business Season v1.0."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any

BUSINESS_SEASON_NAMESPACE = uuid.UUID("a31f5d72-6c84-4b91-9e27-5f3a8d14c620")


class SeasonStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNAVAILABLE = "unavailable"


class SeasonLifecycle(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ValueType(StrEnum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"


class ComparisonOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    IN = "in"


class ConditionKind(StrEnum):
    COMPARISON = "comparison"
    ALL = "all"
    ANY = "any"
    NOT = "not"


def _required(*values: str) -> None:
    if not all(value.strip() and value == value.strip() for value in values):
        raise ValueError("canonical text values must be non-blank and trimmed")


@dataclass(frozen=True, slots=True)
class SemanticInputReference:
    """A source-independent semantic input requested by policy."""

    capability: str
    field: str
    value_type: ValueType

    def __post_init__(self) -> None:
        _required(self.capability, self.field)


@dataclass(frozen=True, slots=True)
class ConditionInputReference:
    """The actual authoritative source selected for a semantic input."""

    source: str
    capability: str
    field: str
    value_type: ValueType

    def __post_init__(self) -> None:
        _required(self.source, self.capability, self.field)


@dataclass(frozen=True, slots=True)
class ConditionOperand:
    kind: ValueType
    value: Any


@dataclass(frozen=True, slots=True)
class Comparison:
    input: SemanticInputReference
    operator: ComparisonOperator
    operand: ConditionOperand

    def __post_init__(self) -> None:
        expected = (
            ValueType.STRING
            if self.input.value_type is ValueType.TEXT
            else self.input.value_type
        )
        if self.operand.kind is not expected:
            raise ValueError("condition operand kind is incompatible with input type")
        if self.operator is ComparisonOperator.CONTAINS and (
            self.input.value_type not in {ValueType.STRING, ValueType.TEXT}
            or not isinstance(self.operand.value, str)
        ):
            raise ValueError(
                "contains requires a string or text input and string operand"
            )
        if self.operator is ComparisonOperator.IN:
            values = self.operand.value
            if not isinstance(values, tuple) or not values:
                raise ValueError("in requires a non-empty immutable operand set")
            if any(not operand_has_type(value, expected) for value in values):
                raise ValueError(
                    "in operand members must match the declared input type"
                )
        elif not operand_has_type(self.operand.value, expected):
            raise ValueError("condition operand value must match its declared kind")


@dataclass(frozen=True, slots=True)
class ConditionExpression:
    condition_id: str
    comparison: Comparison | None = None
    all: tuple["ConditionExpression", ...] | None = None
    any: tuple["ConditionExpression", ...] | None = None
    not_: tuple["ConditionExpression", ...] | None = None

    def __post_init__(self) -> None:
        _required(self.condition_id)
        forms = (self.comparison, self.all, self.any, self.not_)
        if sum(form is not None for form in forms) != 1:
            raise ValueError("condition expression requires exactly one form")
        if self.all == () or self.any == ():
            raise ValueError("all and any condition groups must not be empty")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("not condition requires exactly one child")


@dataclass(frozen=True, slots=True)
class SourcePrecedence:
    semantic_input: SemanticInputReference
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.sources or len(self.sources) != len(set(self.sources)):
            raise ValueError("source precedence requires unique ordered sources")
        _required(*self.sources)


@dataclass(frozen=True, slots=True)
class SeasonResultRule:
    rule_id: str
    condition: ConditionExpression
    outcome: SeasonStatus

    def __post_init__(self) -> None:
        _required(self.rule_id)


@dataclass(frozen=True, slots=True)
class SeasonPolicy:
    policy_id: str
    version: str
    result_rules: tuple[SeasonResultRule, ...]
    provenance: str
    source_precedence: tuple[SourcePrecedence, ...] = ()

    def __post_init__(self) -> None:
        _required(self.policy_id, self.version, self.provenance)
        if not self.result_rules:
            raise ValueError("season policy requires at least one result rule")
        rule_ids = tuple(rule.rule_id for rule in self.result_rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("season policy result rule ids must be unique")
        inputs = tuple(item.semantic_input for item in self.source_precedence)
        if len(inputs) != len(set(inputs)):
            raise ValueError(
                "source precedence entries must be unique per semantic input"
            )


@dataclass(frozen=True, slots=True)
class SeasonAuthoritativeInput:
    source: str
    capability: str
    reference_id: str
    field: str
    value_type: ValueType
    value: Any
    enum_vocabulary: tuple[Enum, ...] = ()

    def __post_init__(self) -> None:
        _required(self.source, self.capability, self.reference_id, self.field)
        if self.value_type is ValueType.ENUM and not self.enum_vocabulary:
            raise ValueError("enum authoritative input requires an explicit vocabulary")

    @property
    def semantic_input(self) -> SemanticInputReference:
        return SemanticInputReference(self.capability, self.field, self.value_type)

    @property
    def condition_reference(self) -> ConditionInputReference:
        return ConditionInputReference(
            self.source, self.capability, self.field, self.value_type
        )


@dataclass(frozen=True, slots=True)
class UnavailableSeasonInformation:
    source: str
    capability: str
    reference_id: str
    field: str
    reason: str

    def __post_init__(self) -> None:
        _required(
            self.source, self.capability, self.reference_id, self.field, self.reason
        )


@dataclass(frozen=True, slots=True)
class SeasonConditionEvaluation:
    condition_id: str
    kind: ConditionKind
    status: SeasonStatus
    input_reference: ConditionInputReference | None = None
    operator: ComparisonOperator | None = None
    operand: ConditionOperand | None = None
    children: tuple["SeasonConditionEvaluation", ...] = ()


@dataclass(frozen=True, slots=True)
class SeasonEvaluationContext:
    business_id: uuid.UUID
    assessment_time: datetime
    inputs: tuple[SeasonAuthoritativeInput, ...]
    provenance: str
    temporal_context: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.provenance)
        if self.temporal_context > self.assessment_time:
            raise ValueError("temporal context cannot be after assessment time")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("limitations must not be blank")


@dataclass(frozen=True, slots=True)
class SeasonTraceability:
    policy_id: str
    policy_version: str
    policy_provenance: str
    selected_inputs: tuple[SeasonAuthoritativeInput, ...]
    condition_evaluations: tuple[SeasonConditionEvaluation, ...]


@dataclass(frozen=True, slots=True)
class BusinessSeason:
    season_id: uuid.UUID
    business_id: uuid.UUID
    season_type: str
    canonical_subject: str
    season_version: str
    status: SeasonStatus
    assessment_time: datetime
    effective_from: datetime
    effective_until: datetime | None
    policy_id: str
    policy_version: str
    lifecycle: SeasonLifecycle
    source_references: tuple[ConditionInputReference, ...]
    evidence: tuple[SeasonAuthoritativeInput, ...]
    limitations: tuple[str, ...]
    input_traceability: tuple[SeasonAuthoritativeInput, ...]
    provenance: str
    temporal_context: datetime
    traceability: SeasonTraceability
    unavailable_information: tuple[UnavailableSeasonInformation, ...] = ()
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(
            self.season_type,
            self.canonical_subject,
            self.season_version,
            self.policy_id,
            self.policy_version,
            self.provenance,
        )
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("season effective period is invalid")
        if self.temporal_context > self.assessment_time:
            raise ValueError("temporal context cannot be after assessment time")
        if (self.lifecycle is SeasonLifecycle.PUBLISHED) != (
            self.published_at is not None
        ):
            raise ValueError("publication timestamp must match lifecycle")
        if self.status is not SeasonStatus.UNAVAILABLE and self.unavailable_information:
            raise ValueError("unavailable information requires unavailable status")

    @property
    def identity_serialization(self) -> str:
        return "|".join(
            (
                str(self.business_id),
                self.season_type,
                self.canonical_subject,
                self.season_version,
            )
        )


def valid_value(
    value: Any, value_type: ValueType, vocabulary: tuple[Enum, ...] = ()
) -> bool:
    valid: bool
    if value_type in {ValueType.STRING, ValueType.TEXT}:
        valid = isinstance(value, str)
    elif value_type is ValueType.INTEGER:
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif value_type is ValueType.DECIMAL:
        valid = isinstance(value, Decimal)
    elif value_type is ValueType.BOOLEAN:
        valid = isinstance(value, bool)
    elif value_type is ValueType.DATE:
        valid = isinstance(value, date) and not isinstance(value, datetime)
    elif value_type is ValueType.DATETIME:
        valid = isinstance(value, datetime)
    else:
        valid = isinstance(value, Enum) and value in vocabulary
    return valid


def operand_has_type(value: Any, value_type: ValueType) -> bool:
    """Validate policy data without coercing an operand into another type."""
    matches: bool
    if value_type in {ValueType.STRING, ValueType.TEXT}:
        matches = isinstance(value, str)
    elif value_type is ValueType.INTEGER:
        matches = isinstance(value, int) and not isinstance(value, bool)
    elif value_type is ValueType.DECIMAL:
        matches = isinstance(value, Decimal)
    elif value_type is ValueType.BOOLEAN:
        matches = isinstance(value, bool)
    elif value_type is ValueType.DATE:
        matches = isinstance(value, date) and not isinstance(value, datetime)
    elif value_type is ValueType.DATETIME:
        matches = isinstance(value, datetime)
    else:
        matches = isinstance(value, Enum)
    return matches
