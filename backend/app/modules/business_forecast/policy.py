"""Immutable declarative structures for FORECAST-004 Policy Evaluation."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from numbers import Number
from typing import Any

from app.modules.business_forecast.models import (
    ForecastTraceability,
    PublishedForecast,
)


class ConditionStatus(StrEnum):
    """The founder-approved condition and overall-status vocabulary."""

    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class ComparisonOperator(StrEnum):
    """The complete approved comparison vocabulary."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    IN = "in"


class ApplicabilityMode(StrEnum):
    ALWAYS = "always"
    WHEN = "when"


class ApplicabilityOutcome(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class EvaluationImpact(StrEnum):
    CONDITION_UNAVAILABLE = "condition_unavailable"
    OVERALL_UNAVAILABLE = "overall_unavailable"
    NO_OVERALL_IMPACT = "no_overall_impact"


class StatusHandlingBehavior(StrEnum):
    CONSIDER = "consider"
    IGNORE = "ignore"
    MAP_TO_UNAVAILABLE = "map_to_unavailable"


@dataclass(frozen=True, slots=True)
class ConditionInputReference:
    source: str
    capability: str
    field: str
    value_type: str

    def __post_init__(self) -> None:
        if not all(
            item.strip()
            for item in (self.source, self.capability, self.field, self.value_type)
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


@dataclass(frozen=True, slots=True)
class Comparison:
    input_reference: ConditionInputReference
    operator: ComparisonOperator
    operand: ConditionOperand


@dataclass(frozen=True, slots=True)
class ConditionExpression:
    comparison: Comparison | None = None
    all: tuple["ConditionExpression", ...] | None = None
    any: tuple["ConditionExpression", ...] | None = None
    not_: tuple["ConditionExpression", ...] | None = None

    def __post_init__(self) -> None:
        choices = (self.comparison, self.all, self.any, self.not_)
        if sum(choice is not None for choice in choices) != 1:
            raise ValueError("condition expression requires exactly one form")
        if self.all == () or self.any == ():
            raise ValueError("condition expression all and any must not be empty")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("condition expression not requires exactly one child")


@dataclass(frozen=True, slots=True)
class ApplicabilityRule:
    mode: ApplicabilityMode
    expression: ConditionExpression | None = None

    def __post_init__(self) -> None:
        if self.mode is ApplicabilityMode.ALWAYS and self.expression is not None:
            raise ValueError("always applicability cannot contain an expression")
        if self.mode is ApplicabilityMode.WHEN and self.expression is None:
            raise ValueError("when applicability requires an expression")


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    condition_id: str
    expression: ConditionExpression
    applicability: ApplicabilityRule
    provenance: str


@dataclass(frozen=True, slots=True)
class StatusReference:
    condition_id: str
    expected_status: ConditionStatus


@dataclass(frozen=True, slots=True)
class StatusExpression:
    status_reference: StatusReference | None = None
    all: tuple["StatusExpression", ...] | None = None
    any: tuple["StatusExpression", ...] | None = None
    not_: tuple["StatusExpression", ...] | None = None

    def __post_init__(self) -> None:
        choices = (self.status_reference, self.all, self.any, self.not_)
        if sum(choice is not None for choice in choices) != 1:
            raise ValueError("status expression requires exactly one form")
        if self.all == () or self.any == ():
            raise ValueError("status expression all and any must not be empty")
        if self.not_ is not None and len(self.not_) != 1:
            raise ValueError("status expression not requires exactly one child")


@dataclass(frozen=True, slots=True)
class AggregationResultRule:
    when: StatusExpression
    result: ConditionStatus


@dataclass(frozen=True, slots=True)
class StatusHandling:
    condition_id: str
    behavior: StatusHandlingBehavior


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    context_id: str
    evaluated_at: datetime
    business_id: uuid.UUID
    values: tuple[tuple[ConditionInputReference, Any], ...]
    traceability: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.context_id.strip() or not self.traceability:
            raise ValueError("evaluation context requires identity and traceability")
        keys = tuple((ref.source, ref.capability, ref.field) for ref, _ in self.values)
        if len(keys) != len(set(keys)):
            raise ValueError("evaluation context values must be unique")

    def resolve(self, reference: ConditionInputReference) -> Any | None:
        for candidate, value in self.values:
            if (candidate.source, candidate.capability, candidate.field) == (
                reference.source,
                reference.capability,
                reference.field,
            ) and candidate.value_type == reference.value_type:
                return value
        return None


@dataclass(frozen=True, slots=True)
class PolicyAggregation:
    participating_conditions: tuple[str, ...]
    status_handling: tuple[StatusHandling, ...]
    result_rules: tuple[AggregationResultRule, ...]

    def __post_init__(self) -> None:
        if not self.participating_conditions:
            raise ValueError("policy aggregation requires participating conditions")
        if len(set(self.participating_conditions)) != len(
            self.participating_conditions
        ):
            raise ValueError("participating conditions must be unique")
        handled = tuple(item.condition_id for item in self.status_handling)
        if set(handled) != set(self.participating_conditions):
            raise ValueError("each participating condition requires status handling")
        if len(handled) != len(set(handled)):
            raise ValueError("status handling entries must be unique")


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    policy_id: str
    version: str
    effective_from: datetime
    effective_until: datetime | None
    applicability: ApplicabilityRule
    conditions: tuple[PolicyCondition, ...]
    aggregation: PolicyAggregation
    provenance: str

    def __post_init__(self) -> None:
        condition_ids = tuple(condition.condition_id for condition in self.conditions)
        if not self.policy_id.strip() or not self.version.strip():
            raise ValueError("policy identity must not be blank")
        if not self.provenance.strip() or not condition_ids:
            raise ValueError("policy requires provenance and conditions")
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("policy condition ids must be unique")
        if (
            self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("policy effective period is invalid")
        if not set(self.aggregation.participating_conditions).issubset(condition_ids):
            raise ValueError("aggregation references undeclared condition")
        for rule in self.aggregation.result_rules:
            references = self._status_references(rule.when)
            if not references.issubset(set(self.aggregation.participating_conditions)):
                raise ValueError("result rule references non-participating condition")

    @staticmethod
    def _status_references(expression: StatusExpression) -> set[str]:
        if expression.status_reference is not None:
            return {expression.status_reference.condition_id}
        children = expression.all or expression.any or expression.not_ or ()
        return set().union(
            *(PolicyDefinition._status_references(child) for child in children)
        )


@dataclass(frozen=True, slots=True)
class PolicyConditionResult:
    condition_id: str
    applicability: ApplicabilityOutcome
    status: ConditionStatus
    authoritative_references: tuple[ConditionInputReference, ...]
    limitation: str | None = None
    evaluation_impact: EvaluationImpact = EvaluationImpact.NO_OVERALL_IMPACT
    unavailable_input_references: tuple[ConditionInputReference, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    evaluation_id: str
    business_id: uuid.UUID
    forecast_identity: PublishedForecast
    policy_id: str
    policy_version: str
    evaluation_context: EvaluationContext
    condition_results: tuple[PolicyConditionResult, ...]
    overall_status: ConditionStatus
    limitations: tuple[str, ...]
    traceability: tuple[str, ...]
    forecast_traceability: ForecastTraceability
    policy_provenance: str
    policy_effective_from: datetime
    policy_effective_until: datetime | None
    evaluation_time: datetime


class BusinessForecastPolicyEvaluator:
    """Evaluate finite Policy data using supplied authoritative values only."""

    def evaluate(
        self,
        *,
        evaluation_id: str,
        forecast: PublishedForecast,
        policy: PolicyDefinition,
        context: EvaluationContext,
        evaluation_time: datetime,
    ) -> PolicyEvaluation:
        if not evaluation_id.strip():
            raise ValueError("evaluation identity must not be blank")
        if forecast.forecast.identity.business_id != context.business_id:
            raise ValueError("forecast and evaluation context business must match")
        if evaluation_time < policy.effective_from or (
            policy.effective_until is not None
            and evaluation_time > policy.effective_until
        ):
            raise ValueError("policy is not effective at evaluation time")
        policy_applies = self._applicable(policy.applicability, context)
        handling_by_condition = {
            item.condition_id: item.behavior
            for item in policy.aggregation.status_handling
        }
        results = tuple(
            self._condition(
                condition,
                context,
                policy_applies,
                handling_by_condition[condition.condition_id],
            )
            for condition in policy.conditions
        )
        statuses = {result.condition_id: result.status for result in results}
        handling = {
            item.condition_id: item.behavior
            for item in policy.aggregation.status_handling
        }
        aggregation_values = {
            identifier: (
                ConditionStatus.UNAVAILABLE
                if handling[identifier] is StatusHandlingBehavior.MAP_TO_UNAVAILABLE
                else status
            )
            for identifier, status in statuses.items()
            if identifier in handling
            and handling[identifier] is not StatusHandlingBehavior.IGNORE
        }
        matching = tuple(
            rule.result
            for rule in policy.aggregation.result_rules
            if self._status_expression(rule.when, aggregation_values)
        )
        overall = (
            matching[0]
            if matching and len(set(matching)) == 1
            else ConditionStatus.UNAVAILABLE
        )
        limitations = tuple(
            result.limitation for result in results if result.limitation is not None
        )
        return PolicyEvaluation(
            evaluation_id=evaluation_id,
            business_id=context.business_id,
            forecast_identity=forecast,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            evaluation_context=context,
            condition_results=results,
            overall_status=overall,
            limitations=limitations,
            traceability=context.traceability,
            forecast_traceability=forecast.forecast.traceability,
            policy_provenance=policy.provenance,
            policy_effective_from=policy.effective_from,
            policy_effective_until=policy.effective_until,
            evaluation_time=evaluation_time,
        )

    def _condition(
        self,
        condition: PolicyCondition,
        context: EvaluationContext,
        policy_applies: bool | None,
        status_handling: StatusHandlingBehavior,
    ) -> PolicyConditionResult:
        applicable = policy_applies
        if applicable:
            applicable = self._applicable(condition.applicability, context)
        if applicable is None:
            return self._unavailable(
                condition,
                ApplicabilityOutcome.UNAVAILABLE,
                status_handling,
                context,
            )
        if not applicable:
            return PolicyConditionResult(
                condition.condition_id,
                ApplicabilityOutcome.NOT_APPLICABLE,
                ConditionStatus.NOT_APPLICABLE,
                (),
            )
        value = self._condition_expression(condition.expression, context)
        if value is None:
            return self._unavailable(
                condition,
                ApplicabilityOutcome.APPLICABLE,
                status_handling,
                context,
            )
        status = ConditionStatus.SATISFIED if value else ConditionStatus.NOT_SATISFIED
        return PolicyConditionResult(
            condition.condition_id,
            ApplicabilityOutcome.APPLICABLE,
            status,
            self._references(condition.expression),
        )

    def _unavailable(
        self,
        condition: PolicyCondition,
        applicability: ApplicabilityOutcome,
        status_handling: StatusHandlingBehavior,
        context: EvaluationContext,
    ) -> PolicyConditionResult:
        return PolicyConditionResult(
            condition.condition_id,
            applicability,
            ConditionStatus.UNAVAILABLE,
            self._references(condition.expression),
            "required authoritative input is unavailable",
            (
                EvaluationImpact.OVERALL_UNAVAILABLE
                if status_handling is StatusHandlingBehavior.MAP_TO_UNAVAILABLE
                else EvaluationImpact.CONDITION_UNAVAILABLE
            ),
            self._unavailable_references(condition.expression, context),
        )

    def _unavailable_references(
        self, expression: ConditionExpression, context: EvaluationContext
    ) -> tuple[ConditionInputReference, ...]:
        return tuple(
            reference
            for reference in self._references(expression)
            if context.resolve(reference) is None
            or not self._valid_type(context.resolve(reference), reference)
        )

    def _applicable(
        self,
        rule: ApplicabilityRule,
        context: EvaluationContext,
    ) -> bool | None:
        if rule.mode is ApplicabilityMode.ALWAYS:
            return True
        return self._condition_expression(rule.expression, context)

    def _condition_expression(
        self,
        expression: ConditionExpression | None,
        context: EvaluationContext,
    ) -> bool | None:
        if expression is None:
            return True
        if expression.comparison is not None:
            comparison = expression.comparison
            value = context.resolve(comparison.input_reference)
            if value is None or not self._valid_type(value, comparison.input_reference):
                return None
            return self._compare(value, comparison)
        children = expression.all or expression.any or expression.not_ or ()
        values = tuple(self._condition_expression(child, context) for child in children)
        if any(value is None for value in values):
            return None
        if expression.not_ is not None:
            return not values[0]
        return all(values) if expression.all is not None else any(values)

    def _valid_type(self, value: Any, reference: ConditionInputReference) -> bool:
        if reference.value_type == "enum":
            return isinstance(value, Enum)
        if reference.value_type == "numeric":
            return isinstance(value, Number) and not isinstance(value, bool)
        if reference.value_type == "text":
            return isinstance(value, str)
        if reference.value_type == "boolean":
            return isinstance(value, bool)
        if reference.value_type == "date":
            return isinstance(value, date) and not isinstance(value, datetime)
        return isinstance(value, datetime)

    def _compare(self, value: Any, comparison: Comparison) -> bool | None:
        operand = comparison.operand.value
        try:
            if comparison.operator is ComparisonOperator.EQUALS:
                result = value == operand
            elif comparison.operator is ComparisonOperator.NOT_EQUALS:
                result = value != operand
            elif comparison.operator is ComparisonOperator.GREATER_THAN:
                result = value > operand
            elif comparison.operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
                result = value >= operand
            elif comparison.operator is ComparisonOperator.LESS_THAN:
                result = value < operand
            elif comparison.operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
                result = value <= operand
            elif comparison.operator is ComparisonOperator.CONTAINS:
                result = operand in value
            else:
                result = value in operand
            return bool(result)
        except TypeError:
            return None

    def _status_expression(
        self,
        expression: StatusExpression,
        values: dict[str, ConditionStatus],
    ) -> bool:
        if expression.status_reference is not None:
            reference = expression.status_reference
            return values.get(reference.condition_id) is reference.expected_status
        children = expression.all or expression.any or expression.not_ or ()
        values_for_children = tuple(
            self._status_expression(child, values) for child in children
        )
        if expression.not_ is not None:
            return not values_for_children[0]
        return (
            all(values_for_children)
            if expression.all is not None
            else any(values_for_children)
        )

    def _references(
        self,
        expression: ConditionExpression,
    ) -> tuple[ConditionInputReference, ...]:
        if expression.comparison is not None:
            return (expression.comparison.input_reference,)
        children = expression.all or expression.any or expression.not_ or ()
        return tuple(
            reference for child in children for reference in self._references(child)
        )
