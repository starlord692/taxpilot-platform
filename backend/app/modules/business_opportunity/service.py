"""Pure deterministic Business Opportunity evaluation from Published Forecast."""

import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.modules.business_forecast.models import (
    ForecastAuthoritativeInput,
    PublishedForecast,
)
from app.modules.business_opportunity.models import (
    BusinessOpportunity,
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionInputReference,
    ConditionStatus,
    OpportunityConditionEvaluation,
    OpportunityPolicy,
    OpportunityStatus,
    StatusExpression,
    UnavailableOpportunityInformation,
)

BUSINESS_OPPORTUNITY_NAMESPACE = uuid.UUID("fb8f1782-cb4d-4012-b0fb-41d45c53a842")


class BusinessOpportunityEvaluator:
    """Evaluate explicit Opportunity policy rules against published inputs only."""

    def evaluate(
        self,
        forecast: PublishedForecast,
        policy: OpportunityPolicy,
        *,
        assessment_time: datetime,
        opportunity_type: str,
        canonical_subject: str,
    ) -> BusinessOpportunity:
        identity = forecast.forecast.identity
        if (
            assessment_time < identity.assessed_at
            or assessment_time < forecast.published_at
        ):
            raise ValueError("opportunity assessment cannot precede published forecast")
        if assessment_time < policy.effective_from or (
            policy.effective_until is not None
            and assessment_time >= policy.effective_until
        ):
            raise ValueError("opportunity policy is not effective")
        self._identity_component(opportunity_type, "opportunity type")
        self._identity_component(canonical_subject, "canonical subject")
        evaluations = tuple(
            self._condition(item, forecast, policy) for item in policy.conditions
        )
        statuses = {item.condition_id: item.status for item in evaluations}
        result = self._result(policy, statuses)
        unavailable = tuple(
            info for item in evaluations for info in self._unavailable(item, forecast)
        )
        limitations = tuple(
            item.description for item in forecast.forecast.limitations
        ) + tuple(info.reason for info in unavailable)
        evidence = tuple(
            item
            for item in forecast.authoritative_inputs
            if self._is_evidence(item, policy.conditions)
        )
        serialized = self._serialize(
            identity.business_id,
            opportunity_type,
            canonical_subject,
            policy.policy_id,
            policy.version,
        )
        return BusinessOpportunity(
            uuid.uuid5(BUSINESS_OPPORTUNITY_NAMESPACE, serialized),
            identity.business_id,
            result,
            assessment_time,
            opportunity_type,
            canonical_subject,
            policy.policy_id,
            policy.version,
            result,
            forecast.authoritative_inputs,
            evidence,
            limitations,
            forecast.authoritative_inputs,
            policy.provenance,
            identity.assessed_at,
            evaluations,
            unavailable,
        )

    @staticmethod
    def _identity_component(value: str, label: str) -> None:
        if not value or value != value.strip():
            raise ValueError(f"{label} must not be blank or contain outer whitespace")

    @staticmethod
    def _serialize(
        business_id: uuid.UUID,
        opportunity_type: str,
        subject: str,
        policy_id: str,
        policy_version: str,
    ) -> str:
        values = (
            str(business_id),
            opportunity_type,
            subject,
            policy_id,
            policy_version,
        )
        if any(not value or value != value.strip() for value in values):
            raise ValueError(
                "opportunity identity components must not contain outer whitespace"
            )
        return "|".join(values)

    def _condition(
        self,
        expression: ConditionExpression,
        forecast: PublishedForecast,
        policy: OpportunityPolicy,
    ) -> OpportunityConditionEvaluation:
        if expression.comparison is not None:
            comparison = expression.comparison
            item = self._resolve(comparison.input_reference, forecast)
            status = self._comparison_status(item, comparison, policy)
            return OpportunityConditionEvaluation(
                expression.condition_id,
                status,
                comparison.input_reference,
                comparison.operator,
                comparison.operand,
            )
        children = tuple(
            self._condition(child, forecast, policy)
            for child in (expression.all or expression.any or expression.not_ or ())
        )
        statuses = tuple(child.status for child in children)
        if expression.not_ is not None:
            status = {
                ConditionStatus.SATISFIED: ConditionStatus.NOT_SATISFIED,
                ConditionStatus.NOT_SATISFIED: ConditionStatus.SATISFIED,
                ConditionStatus.UNAVAILABLE: ConditionStatus.UNAVAILABLE,
            }[statuses[0]]
        elif expression.all is not None:
            status = (
                ConditionStatus.NOT_SATISFIED
                if ConditionStatus.NOT_SATISFIED in statuses
                else ConditionStatus.SATISFIED
                if all(value is ConditionStatus.SATISFIED for value in statuses)
                else ConditionStatus.UNAVAILABLE
            )
        else:
            status = (
                ConditionStatus.SATISFIED
                if ConditionStatus.SATISFIED in statuses
                else ConditionStatus.NOT_SATISFIED
                if all(value is ConditionStatus.NOT_SATISFIED for value in statuses)
                else ConditionStatus.UNAVAILABLE
            )
        return OpportunityConditionEvaluation(
            expression.condition_id, status, children=children
        )

    @staticmethod
    def _resolve(
        reference: ConditionInputReference, forecast: PublishedForecast
    ) -> ForecastAuthoritativeInput | None:
        for item in forecast.authoritative_inputs:
            if (item.source, item.capability, item.field, item.value_type) == (
                reference.source,
                reference.capability,
                reference.field,
                reference.value_type,
            ):
                return item
        return None

    def _comparison_status(
        self,
        item: ForecastAuthoritativeInput | None,
        comparison: Comparison,
        policy: OpportunityPolicy,
    ) -> ConditionStatus:
        if item is None or not self._valid_value(
            item.value, comparison.input_reference.value_type
        ):
            return ConditionStatus.UNAVAILABLE
        if comparison.input_reference.value_type == "enum" and not self._enum_valid(
            item.value, comparison.input_reference, policy
        ):
            return ConditionStatus.UNAVAILABLE
        result = self._compare(item.value, comparison)
        return (
            ConditionStatus.UNAVAILABLE
            if result is None
            else ConditionStatus.SATISFIED
            if result
            else ConditionStatus.NOT_SATISFIED
        )

    @staticmethod
    def _valid_value(value: Any, value_type: str) -> bool:
        if value_type == "numeric":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if value_type == "text":
            return isinstance(value, str)
        if value_type == "boolean":
            return isinstance(value, bool)
        if value_type == "date":
            return isinstance(value, date) and not isinstance(value, datetime)
        if value_type == "datetime":
            return isinstance(value, datetime)
        return isinstance(value, str)

    @staticmethod
    def _enum_valid(
        value: Any, reference: ConditionInputReference, policy: OpportunityPolicy
    ) -> bool:
        vocabulary = next(
            (
                item.values
                for item in policy.enum_vocabularies
                if item.input_reference == reference
            ),
            None,
        )
        return vocabulary is not None and value in vocabulary

    @staticmethod
    def _compare(value: Any, comparison: Comparison) -> bool | None:
        operand = comparison.operand.value
        comparisons: dict[ComparisonOperator, Callable[[], bool]] = {
            ComparisonOperator.EQUALS: lambda: value == operand,
            ComparisonOperator.NOT_EQUALS: lambda: value != operand,
            ComparisonOperator.GREATER_THAN: lambda: value > operand,
            ComparisonOperator.GREATER_THAN_OR_EQUAL: lambda: value >= operand,
            ComparisonOperator.LESS_THAN: lambda: value < operand,
            ComparisonOperator.LESS_THAN_OR_EQUAL: lambda: value <= operand,
            ComparisonOperator.CONTAINS: lambda: operand in value,
            ComparisonOperator.IN: lambda: value in operand,
        }
        try:
            return comparisons[comparison.operator]()
        except TypeError:
            return None

    def _result(
        self, policy: OpportunityPolicy, statuses: dict[str, ConditionStatus]
    ) -> OpportunityStatus:
        matches = tuple(
            rule.result
            for rule in policy.result_rules
            if self._status_expression(rule.expression, statuses)
        )
        if len(matches) == 1:
            return matches[0]
        if any(value is ConditionStatus.UNAVAILABLE for value in statuses.values()):
            return OpportunityStatus.UNAVAILABLE
        raise ValueError(
            "opportunity policy lacks exactly one deterministic result rule"
        )

    def _status_expression(
        self, expression: StatusExpression, statuses: dict[str, ConditionStatus]
    ) -> bool:
        if expression.condition_id is not None:
            return statuses.get(expression.condition_id) is expression.expected_status
        children = tuple(
            self._status_expression(child, statuses)
            for child in (expression.all or expression.any or expression.not_ or ())
        )
        return (
            not children[0]
            if expression.not_ is not None
            else all(children)
            if expression.all is not None
            else any(children)
        )

    def _unavailable(
        self, evaluation: OpportunityConditionEvaluation, forecast: PublishedForecast
    ) -> tuple[UnavailableOpportunityInformation, ...]:
        children = tuple(
            info
            for child in evaluation.children
            for info in self._unavailable(child, forecast)
        )
        if (
            evaluation.input_reference is None
            or evaluation.status is not ConditionStatus.UNAVAILABLE
        ):
            return children
        item = self._resolve(evaluation.input_reference, forecast)
        reason = (
            "required authoritative input is unavailable"
            if item is None
            else "authoritative input is invalid for declared value type"
        )
        return children + (
            UnavailableOpportunityInformation(
                evaluation.input_reference.source,
                evaluation.input_reference.capability,
                None if item is None else item.reference_id,
                evaluation.input_reference.field,
                reason,
            ),
        )

    @staticmethod
    def _is_evidence(
        item: ForecastAuthoritativeInput, expressions: tuple[ConditionExpression, ...]
    ) -> bool:
        return any(
            BusinessOpportunityEvaluator._references(expression, item)
            for expression in expressions
        )

    @staticmethod
    def _references(
        expression: ConditionExpression, item: ForecastAuthoritativeInput
    ) -> bool:
        if expression.comparison is not None:
            reference = expression.comparison.input_reference
            return (
                reference.source,
                reference.capability,
                reference.field,
                reference.value_type,
            ) == (item.source, item.capability, item.field, item.value_type)
        return any(
            BusinessOpportunityEvaluator._references(child, item)
            for child in (expression.all or expression.any or expression.not_ or ())
        )
