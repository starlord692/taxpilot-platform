"""Pure deterministic evaluation for Business Risk v1.0."""

import uuid
from typing import Any

from app.modules.business_forecast.models import PublishedForecast
from app.modules.business_risk.models import (
    ApplicabilityOutcome,
    BusinessRisk,
    ComparisonOperator,
    ConditionKind,
    ConditionStatus,
    RiskAssessmentPolicy,
    RiskCategory,
    RiskConditionEvaluation,
    RiskConditionExpression,
    RiskEvaluationContext,
    RiskEvaluationResult,
    RiskEvidenceReference,
    RiskInputReference,
    RiskStatus,
    RiskTraceability,
    UnavailableRiskInformation,
)

BUSINESS_RISK_NAMESPACE = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")


class BusinessRiskEvaluator:
    """Evaluate approved Risk policy from published Forecast inputs only."""

    def evaluate(
        self,
        forecast: PublishedForecast,
        policy: RiskAssessmentPolicy,
        context: RiskEvaluationContext,
    ) -> RiskEvaluationResult:
        if forecast.forecast.identity.business_id != context.business_id:
            raise ValueError("forecast and risk context business must match")
        if context.evaluated_at < policy.effective_from or (
            policy.effective_until is not None
            and context.evaluated_at >= policy.effective_until
        ):
            raise ValueError("risk policy is not effective")
        policy_outcome, policy_tree = self._applicability(
            policy.applicability,
            forecast,
        )
        if policy_outcome is not ApplicabilityOutcome.APPLICABLE:
            unavailable = self._unavailable_information(policy_tree)
            return RiskEvaluationResult(
                policy_outcome,
                policy_tree,
                (),
                self._limitations(forecast, unavailable),
                unavailable,
            )
        results = []
        for rule in policy.risk_rules:
            outcome, applicability_tree = self._applicability(
                rule.applicability, forecast
            )
            if outcome is ApplicabilityOutcome.NOT_APPLICABLE:
                continue
            tree = (
                applicability_tree
                if outcome is ApplicabilityOutcome.UNAVAILABLE
                else self._condition(rule.condition, forecast)
            )
            if tree is None:
                raise ValueError("unavailable rule applicability requires evaluation")
            status = (
                RiskStatus.UNAVAILABLE
                if tree.status is ConditionStatus.UNAVAILABLE
                else (
                    RiskStatus.IDENTIFIED
                    if tree.status is ConditionStatus.SATISFIED
                    else RiskStatus.NOT_IDENTIFIED
                )
            )
            category: RiskCategory | None = (
                rule.category if status is RiskStatus.IDENTIFIED else None
            )
            severity = rule.severity if status is RiskStatus.IDENTIFIED else None
            identity = forecast.forecast.identity
            text = "|".join(
                (
                    str(context.business_id),
                    str(identity.assessed_at),
                    identity.horizon.reference,
                    identity.published_version,
                    policy.policy_id,
                    policy.version,
                    rule.risk_rule_id,
                )
            )
            references = self._references(tree)
            evidence = tuple(
                RiskEvidenceReference(
                    item.source,
                    item.capability,
                    item.reference_id,
                    item.field,
                )
                for ref in references
                for item in forecast.authoritative_inputs
                if self._matches(ref, item)
            )
            unavailable = self._unavailable_information(tree)
            limitations = self._limitations(forecast, unavailable)
            trace = RiskTraceability(
                context.evaluation_id,
                identity,
                policy.policy_id,
                policy.version,
                rule.risk_rule_id,
                evidence,
            )
            results.append(
                BusinessRisk(
                    uuid.uuid5(BUSINESS_RISK_NAMESPACE, text),
                    context.business_id,
                    identity,
                    policy.policy_id,
                    policy.version,
                    rule.risk_rule_id,
                    context.evaluated_at,
                    status,
                    category,
                    severity,
                    tree,
                    evidence,
                    limitations,
                    trace,
                    unavailable,
                )
            )
        return RiskEvaluationResult(
            ApplicabilityOutcome.APPLICABLE,
            policy_tree,
            tuple(results),
            (),
            (),
        )

    def _applicability(
        self, rule: Any, forecast: PublishedForecast
    ) -> tuple[ApplicabilityOutcome, RiskConditionEvaluation | None]:
        if rule.expression is None:
            return ApplicabilityOutcome.APPLICABLE, None
        result = self._condition(rule.expression, forecast)
        return (
            ApplicabilityOutcome.APPLICABLE
            if result.status is ConditionStatus.SATISFIED
            else ApplicabilityOutcome.NOT_APPLICABLE
            if result.status is ConditionStatus.NOT_SATISFIED
            else ApplicabilityOutcome.UNAVAILABLE
        ), result

    def _condition(
        self, expression: RiskConditionExpression, forecast: PublishedForecast
    ) -> RiskConditionEvaluation:
        if expression.input_reference is not None:
            ref = expression.input_reference
            value = self._resolve(ref, forecast)
            status = (
                ConditionStatus.UNAVAILABLE
                if value is None
                else self._compare(value, expression.operator, expression.operand)
            )
            return RiskConditionEvaluation(
                ConditionKind.COMPARISON,
                status,
                expression.condition_id,
                ref,
                expression.operator,
                expression.operand,
            )
        children = tuple(
            self._condition(child, forecast)
            for child in (expression.all or expression.any or expression.not_ or ())
        )
        statuses = tuple(child.status for child in children)
        if expression.not_ is not None:
            status = {
                ConditionStatus.SATISFIED: ConditionStatus.NOT_SATISFIED,
                ConditionStatus.NOT_SATISFIED: ConditionStatus.SATISFIED,
                ConditionStatus.UNAVAILABLE: ConditionStatus.UNAVAILABLE,
            }[statuses[0]]
            kind = ConditionKind.NOT
        elif expression.all is not None:
            status = (
                ConditionStatus.NOT_SATISFIED
                if ConditionStatus.NOT_SATISFIED in statuses
                else ConditionStatus.SATISFIED
                if all(s is ConditionStatus.SATISFIED for s in statuses)
                else ConditionStatus.UNAVAILABLE
            )
            kind = ConditionKind.ALL
        else:
            status = (
                ConditionStatus.SATISFIED
                if ConditionStatus.SATISFIED in statuses
                else ConditionStatus.NOT_SATISFIED
                if all(s is ConditionStatus.NOT_SATISFIED for s in statuses)
                else ConditionStatus.UNAVAILABLE
            )
            kind = ConditionKind.ANY
        return RiskConditionEvaluation(
            kind, status, expression.condition_id, children=children
        )

    @staticmethod
    def _unavailable_information(
        tree: RiskConditionEvaluation | None,
    ) -> tuple[UnavailableRiskInformation, ...]:
        if tree is None:
            return ()
        items: list[UnavailableRiskInformation] = []
        if tree.status is ConditionStatus.UNAVAILABLE:
            references = BusinessRiskEvaluator._references(tree)
            items.append(
                UnavailableRiskInformation(
                    tree.condition_id,
                    references[0] if len(references) == 1 else None,
                    tree.status,
                    "required authoritative information is unavailable",
                )
            )
        for child in tree.children:
            items.extend(BusinessRiskEvaluator._unavailable_information(child))
        return tuple(items)

    @staticmethod
    def _limitations(
        forecast: PublishedForecast,
        unavailable: tuple[UnavailableRiskInformation, ...],
    ) -> tuple[str, ...]:
        inherited = tuple(item.description for item in forecast.forecast.limitations)
        return inherited + tuple(item.limitation for item in unavailable)

    @staticmethod
    def _resolve(ref: RiskInputReference, forecast: PublishedForecast) -> Any | None:
        for item in forecast.authoritative_inputs:
            if BusinessRiskEvaluator._matches(ref, item):
                return item.value
        return None

    @staticmethod
    def _matches(ref: RiskInputReference, item: Any) -> bool:
        return (item.source, item.capability, item.field, item.value_type) == (
            ref.source,
            ref.capability,
            ref.field,
            ref.value_type,
        )

    @staticmethod
    def _compare(
        value: Any, operator: ComparisonOperator | None, operand: Any
    ) -> ConditionStatus:
        try:
            if operator is ComparisonOperator.EQUALS:
                result = value == operand
            elif operator is ComparisonOperator.NOT_EQUALS:
                result = value != operand
            elif operator is ComparisonOperator.GREATER_THAN:
                result = value > operand
            elif operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
                result = value >= operand
            elif operator is ComparisonOperator.LESS_THAN:
                result = value < operand
            elif operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
                result = value <= operand
            elif operator is ComparisonOperator.CONTAINS:
                result = operand in value
            else:
                return ConditionStatus.UNAVAILABLE
            return (
                ConditionStatus.SATISFIED if result else ConditionStatus.NOT_SATISFIED
            )
        except TypeError:
            return ConditionStatus.UNAVAILABLE

    @staticmethod
    def _references(tree: RiskConditionEvaluation) -> tuple[RiskInputReference, ...]:
        return (
            () if tree.input_reference is None else (tree.input_reference,)
        ) + tuple(
            ref
            for child in tree.children
            for ref in BusinessRiskEvaluator._references(child)
        )
