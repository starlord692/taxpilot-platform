"""Focused deterministic tests for the frozen Business Risk v1.0 contract."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.modules.business_forecast.models import (
    BusinessForecast,
    ForecastAssumption,
    ForecastAuthoritativeInput,
    ForecastExplanationReferences,
    ForecastHorizon,
    ForecastIdentity,
    ForecastLimitation,
    ForecastSourceReference,
    ForecastTraceability,
    PublishedForecast,
)
from app.modules.business_risk.models import (
    ComparisonOperator,
    ConditionStatus,
    RiskApplicability,
    RiskAssessmentPolicy,
    RiskCategory,
    RiskConditionExpression,
    RiskEvaluationContext,
    RiskInputReference,
    RiskRule,
    RiskSeverity,
    RiskStatus,
)
from app.modules.business_risk.service import (
    BUSINESS_RISK_NAMESPACE,
    BusinessRiskEvaluator,
)


def _time() -> datetime:
    return datetime(2026, 8, 15, tzinfo=UTC)


def _reference() -> RiskInputReference:
    return RiskInputReference("PublishedForecast", "Business Health", "state", "text")


def _condition(
    condition_id: str = "health-at-risk",
    operand: object = "at_risk",
) -> RiskConditionExpression:
    return RiskConditionExpression(
        condition_id=condition_id,
        input_reference=_reference(),
        operator=ComparisonOperator.EQUALS,
        operand=operand,
    )


def _forecast(
    business_id: uuid.UUID,
    value: object = "at_risk",
) -> PublishedForecast:
    identity = ForecastIdentity(
        business_id=business_id,
        assessed_at=_time(),
        horizon=ForecastHorizon("90 days"),
        published_version="1.0",
    )
    traceability = ForecastTraceability(
        source_references=(
            ForecastSourceReference("Business Health", "health-1", "prov-1", _time()),
        ),
        policy_version="forecast-policy-1",
        explanation_references=ForecastExplanationReferences(("forecast-exp-1",)),
    )
    forecast = BusinessForecast(
        identity=identity,
        projection="authoritative projection",
        assumptions=(ForecastAssumption("a-1", "assumption", "source-1"),),
        limitations=(ForecastLimitation("l-1", "limitation", "source-1"),),
        traceability=traceability,
        created_at=_time(),
    )
    return PublishedForecast(
        forecast=forecast,
        published_at=_time(),
        authoritative_inputs=(
            ForecastAuthoritativeInput(
                "PublishedForecast",
                "Business Health",
                "health-input-1",
                "state",
                "text",
                value,
            ),
        ),
    )


def _policy(
    *,
    policy_applicability: RiskApplicability | None = None,
    rule_applicability: RiskApplicability | None = None,
    condition: RiskConditionExpression | None = None,
) -> RiskAssessmentPolicy:
    rule = RiskRule(
        "risk-rule-1",
        RiskCategory.FINANCIAL,
        RiskSeverity.HIGH,
        rule_applicability or RiskApplicability(),
        condition or _condition(),
        "founder-approved",
    )
    return RiskAssessmentPolicy(
        "risk-policy-1",
        "1.0",
        _time(),
        None,
        policy_applicability or RiskApplicability(),
        (rule,),
        "founder-approved",
    )


def _context(business_id: uuid.UUID) -> RiskEvaluationContext:
    return RiskEvaluationContext("risk-evaluation-1", business_id, _time())


def test_identified_risk_preserves_authoritative_evidence_and_identity() -> None:
    business_id = uuid.uuid4()
    result = BusinessRiskEvaluator().evaluate(
        _forecast(business_id), _policy(), _context(business_id)
    )
    assert result.policy_applicability.value == "applicable"
    assert len(result.risks) == 1
    risk = result.risks[0]
    assert risk.status is RiskStatus.IDENTIFIED
    assert risk.category is RiskCategory.FINANCIAL
    assert risk.severity is RiskSeverity.HIGH
    assert risk.evidence[0].reference_id == "health-input-1"
    assert risk.condition_evaluation.operator is ComparisonOperator.EQUALS
    assert risk.condition_evaluation.operand == "at_risk"
    assert risk.risk_id == uuid.uuid5(
        BUSINESS_RISK_NAMESPACE,
        "|".join(
            (
                str(business_id),
                str(_time()),
                "90 days",
                "1.0",
                "risk-policy-1",
                "1.0",
                "risk-rule-1",
            )
        ),
    )


def test_not_identified_risk_has_no_category_or_severity() -> None:
    business_id = uuid.uuid4()
    result = BusinessRiskEvaluator().evaluate(
        _forecast(business_id, "healthy"), _policy(), _context(business_id)
    )
    assert result.risks[0].status is RiskStatus.NOT_IDENTIFIED
    assert result.risks[0].category is None
    assert result.risks[0].severity is None


def test_missing_authoritative_input_produces_unavailable_risk() -> None:
    business_id = uuid.uuid4()
    forecast = _forecast(business_id)
    forecast = PublishedForecast(forecast.forecast, forecast.published_at)
    result = BusinessRiskEvaluator().evaluate(
        forecast,
        _policy(),
        _context(business_id),
    )
    assert result.risks[0].status is RiskStatus.UNAVAILABLE
    assert result.risks[0].category is None
    assert result.risks[0].severity is None
    assert result.risks[0].unavailable_information[0].input_reference == _reference()


def test_policy_not_applicable_or_unavailable_publishes_no_risks() -> None:
    business_id = uuid.uuid4()
    not_applicable = RiskApplicability(_condition(operand="healthy"))
    unavailable = RiskApplicability(
        RiskConditionExpression(
            "missing",
            RiskInputReference(
                "PublishedForecast",
                "Business Health",
                "missing",
                "text",
            ),
            ComparisonOperator.EQUALS,
            "value",
        )
    )
    evaluator = BusinessRiskEvaluator()
    not_applicable_result = evaluator.evaluate(
            _forecast(business_id),
            _policy(policy_applicability=not_applicable),
            _context(business_id),
    )
    unavailable_result = evaluator.evaluate(
            _forecast(business_id),
            _policy(policy_applicability=unavailable),
            _context(business_id),
    )
    assert not_applicable_result.risks == ()
    assert unavailable_result.risks == ()
    assert unavailable_result.policy_condition_evaluation is not None
    assert unavailable_result.unavailable_information[0].condition_id == "missing"


def test_rule_not_applicable_publishes_no_risk_and_unavailable_publishes_one() -> None:
    business_id = uuid.uuid4()
    unavailable = RiskApplicability(
        RiskConditionExpression(
            "missing",
            RiskInputReference(
                "PublishedForecast",
                "Business Health",
                "missing",
                "text",
            ),
            ComparisonOperator.EQUALS,
            "value",
        )
    )
    evaluator = BusinessRiskEvaluator()
    not_applicable_result = evaluator.evaluate(
            _forecast(business_id),
            _policy(
                rule_applicability=RiskApplicability(_condition(operand="healthy"))
            ),
            _context(business_id),
    )
    unavailable_result = evaluator.evaluate(
            _forecast(business_id),
            _policy(rule_applicability=unavailable),
            _context(business_id),
    )
    assert not_applicable_result.risks == ()
    assert unavailable_result.risks[0].status is RiskStatus.UNAVAILABLE


def test_all_any_and_not_apply_frozen_three_valued_logic() -> None:
    business_id = uuid.uuid4()
    satisfied = _condition("satisfied")
    missing = RiskConditionExpression(
        "missing",
        RiskInputReference(
            "PublishedForecast",
            "Business Health",
            "missing",
            "text",
        ),
        ComparisonOperator.EQUALS,
        "value",
    )
    evaluator = BusinessRiskEvaluator()
    any_result = evaluator._condition(
        RiskConditionExpression("any", any=(satisfied, missing)), _forecast(business_id)
    )
    all_result = evaluator._condition(
        RiskConditionExpression("all", all=(satisfied, missing)), _forecast(business_id)
    )
    not_result = evaluator._condition(
        RiskConditionExpression("not", not_=(satisfied,)), _forecast(business_id)
    )
    assert any_result.status is ConditionStatus.SATISFIED
    assert all_result.status is ConditionStatus.UNAVAILABLE
    assert not_result.status is ConditionStatus.NOT_SATISFIED


def test_business_mismatch_and_invalid_period_are_rejected() -> None:
    business_id = uuid.uuid4()
    with pytest.raises(ValueError, match="business"):
        BusinessRiskEvaluator().evaluate(
            _forecast(business_id),
            _policy(),
            _context(uuid.uuid4()),
        )
    expired = RiskAssessmentPolicy(
        "risk-policy-1",
        "1.0",
        _time().replace(year=2025),
        _time(),
        RiskApplicability(),
        _policy().risk_rules,
        "founder-approved",
    )
    with pytest.raises(ValueError, match="not effective"):
        BusinessRiskEvaluator().evaluate(
            _forecast(business_id),
            expired,
            _context(business_id),
        )


def test_multiple_rules_remain_independent_without_aggregation() -> None:
    business_id = uuid.uuid4()
    first = _policy().risk_rules[0]
    second = RiskRule(
        "risk-rule-2",
        RiskCategory.OPERATIONAL,
        RiskSeverity.MODERATE,
        RiskApplicability(),
        _condition("other", "healthy"),
        "founder-approved",
    )
    policy = RiskAssessmentPolicy(
        "risk-policy-1",
        "1.0",
        _time(),
        None,
        RiskApplicability(),
        (first, second),
        "founder-approved",
    )
    result = BusinessRiskEvaluator().evaluate(
        _forecast(business_id), policy, _context(business_id)
    )
    assert tuple(risk.risk_rule_id for risk in result.risks) == (
        "risk-rule-1",
        "risk-rule-2",
    )
    assert tuple(risk.status for risk in result.risks) == (
        RiskStatus.IDENTIFIED,
        RiskStatus.NOT_IDENTIFIED,
    )


def test_policy_version_and_rule_identity_change_deterministic_risk_identity() -> None:
    business_id = uuid.uuid4()
    forecast = _forecast(business_id)
    context = _context(business_id)
    base = _policy()
    newer_policy = RiskAssessmentPolicy(
        base.policy_id,
        "2.0",
        base.effective_from,
        base.effective_until,
        base.applicability,
        base.risk_rules,
        base.provenance,
    )
    evaluator = BusinessRiskEvaluator()
    first = evaluator.evaluate(forecast, base, context)
    second = evaluator.evaluate(forecast, base, context)
    newer = evaluator.evaluate(forecast, newer_policy, context)
    assert first.risks[0].risk_id == second.risks[0].risk_id
    assert first.risks[0].risk_id != newer.risks[0].risk_id
    assert str(first.risks[0].risk_id) != context.evaluation_id


def test_policy_effective_from_is_inclusive_and_until_is_exclusive() -> None:
    business_id = uuid.uuid4()
    result = BusinessRiskEvaluator().evaluate(
        _forecast(business_id), _policy(), _context(business_id)
    )
    assert result.risks
    policy = _policy()
    exclusive = RiskAssessmentPolicy(
        policy.policy_id,
        policy.version,
        policy.effective_from.replace(year=2025),
        _time(),
        policy.applicability,
        policy.risk_rules,
        policy.provenance,
    )
    with pytest.raises(ValueError, match="not effective"):
        BusinessRiskEvaluator().evaluate(
            _forecast(business_id), exclusive, _context(business_id)
        )


def test_models_and_published_outputs_are_immutable() -> None:
    business_id = uuid.uuid4()
    result = BusinessRiskEvaluator().evaluate(
        _forecast(business_id), _policy(), _context(business_id)
    )
    with pytest.raises(FrozenInstanceError):
        result.risks[0].status = RiskStatus.UNAVAILABLE  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        _policy().version = "2.0"  # type: ignore[misc]
