"""Focused deterministic tests for the frozen Business Opportunity v1.0 contract."""

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
from app.modules.business_opportunity.models import (
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionInputReference,
    ConditionOperand,
    ConditionStatus,
    EligibilityResultRule,
    EnumVocabulary,
    OpportunityPolicy,
    OpportunityStatus,
    StatusExpression,
)
from app.modules.business_opportunity.service import (
    BUSINESS_OPPORTUNITY_NAMESPACE,
    BusinessOpportunityEvaluator,
)


def _time() -> datetime:
    return datetime(2026, 8, 16, tzinfo=UTC)


def _reference(
    field: str = "state", value_type: str = "enum"
) -> ConditionInputReference:
    return ConditionInputReference(
        "PublishedForecast", "Business Health", field, value_type
    )


def _condition(
    condition_id: str = "health-good", field: str = "state", value: object = "good"
) -> ConditionExpression:
    reference = _reference(field)
    return ConditionExpression(
        condition_id,
        Comparison(
            reference, ComparisonOperator.EQUALS, ConditionOperand("enum", value)
        ),
    )


def _forecast(business_id: uuid.UUID, value: object = "good") -> PublishedForecast:
    identity = ForecastIdentity(business_id, _time(), ForecastHorizon("90 days"), "1.0")
    traceability = ForecastTraceability(
        (ForecastSourceReference("Business Health", "health-1", "prov-1", _time()),),
        "forecast-policy-1",
        ForecastExplanationReferences(("forecast-exp-1",)),
    )
    forecast = BusinessForecast(
        identity,
        "projection",
        (ForecastAssumption("a-1", "assumption", "source-1"),),
        (ForecastLimitation("l-1", "limitation", "source-1"),),
        traceability,
        _time(),
    )
    return PublishedForecast(
        forecast,
        _time(),
        (
            ForecastAuthoritativeInput(
                "PublishedForecast",
                "Business Health",
                "health-input-1",
                "state",
                "enum",
                value,
            ),
        ),
    )


def _policy(
    expression: ConditionExpression | None = None,
    *,
    values: tuple[object, ...] = ("good", "bad"),
    rules: tuple[EligibilityResultRule, ...] | None = None,
) -> OpportunityPolicy:
    condition = expression or _condition()
    result_rules = (
        rules
        if rules is not None
        else (
            EligibilityResultRule(
                StatusExpression(condition.condition_id, ConditionStatus.SATISFIED),
                OpportunityStatus.ELIGIBLE,
            ),
            EligibilityResultRule(
                StatusExpression(condition.condition_id, ConditionStatus.NOT_SATISFIED),
                OpportunityStatus.INELIGIBLE,
            ),
            EligibilityResultRule(
                StatusExpression(condition.condition_id, ConditionStatus.UNAVAILABLE),
                OpportunityStatus.UNAVAILABLE,
            ),
        )
    )
    reference = (
        condition.comparison.input_reference
        if condition.comparison is not None
        else _reference()
    )
    return OpportunityPolicy(
        "opportunity-policy-1",
        "1.0",
        _time(),
        None,
        (condition,),
        result_rules,
        "founder-approved",
        (EnumVocabulary(reference, values),),
    )


def _evaluate(value: object = "good", policy: OpportunityPolicy | None = None):
    business_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    return BusinessOpportunityEvaluator().evaluate(
        _forecast(business_id, value),
        policy or _policy(),
        assessment_time=_time(),
        opportunity_type="growth",
        canonical_subject="repeat-business",
    )


def test_eligible_opportunity_preserves_identity_and_traceability() -> None:
    result = _evaluate()
    expected = (
        "12345678-1234-5678-1234-567812345678|growth|repeat-business|"
        "opportunity-policy-1|1.0"
    )
    assert result.status is OpportunityStatus.ELIGIBLE
    assert result.opportunity_id == uuid.uuid5(BUSINESS_OPPORTUNITY_NAMESPACE, expected)
    assert result.evidence[0].reference_id == "health-input-1"
    assert result.input_traceability == result.source_references


def test_ineligible_and_unavailable_results_are_explicit() -> None:
    assert _evaluate("bad").status is OpportunityStatus.INELIGIBLE
    missing = PublishedForecast(
        _forecast(uuid.UUID("12345678-1234-5678-1234-567812345678")).forecast, _time()
    )
    result = BusinessOpportunityEvaluator().evaluate(
        missing,
        _policy(),
        assessment_time=_time(),
        opportunity_type="growth",
        canonical_subject="repeat-business",
    )
    assert result.status is OpportunityStatus.UNAVAILABLE
    assert result.unavailable_information[0].field == "state"


def test_three_valued_all_any_and_not_preserve_unavailable() -> None:
    available = _condition("available")
    missing = ConditionExpression(
        "missing",
        Comparison(
            _reference("missing"),
            ComparisonOperator.EQUALS,
            ConditionOperand("enum", "good"),
        ),
    )
    evaluator = BusinessOpportunityEvaluator()
    forecast = _forecast(uuid.uuid4())
    all_result = evaluator._condition(
        ConditionExpression("all", all=(available, missing)),
        forecast,
        _policy(available),
    )
    any_result = evaluator._condition(
        ConditionExpression("any", any=(available, missing)),
        forecast,
        _policy(available),
    )
    not_result = evaluator._condition(
        ConditionExpression("not", not_=(missing,)), forecast, _policy(available)
    )
    assert all_result.status is ConditionStatus.UNAVAILABLE
    assert any_result.status is ConditionStatus.SATISFIED
    assert not_result.status is ConditionStatus.UNAVAILABLE


def test_invalid_value_and_enum_vocabulary_are_unavailable() -> None:
    assert _evaluate("unknown").status is OpportunityStatus.UNAVAILABLE
    numeric = ConditionExpression(
        "numeric",
        Comparison(
            ConditionInputReference(
                "PublishedForecast", "Business Health", "state", "numeric"
            ),
            ComparisonOperator.EQUALS,
            ConditionOperand("numeric", 1),
        ),
    )
    policy = OpportunityPolicy(
        "p",
        "1",
        _time(),
        None,
        (numeric,),
        (
            EligibilityResultRule(
                StatusExpression("numeric", ConditionStatus.UNAVAILABLE),
                OpportunityStatus.UNAVAILABLE,
            ),
        ),
        "founder",
    )
    assert _evaluate(policy=policy).status is OpportunityStatus.UNAVAILABLE


def test_invalid_or_ambiguous_policy_and_identity_components_are_rejected() -> None:
    condition = _condition()
    with pytest.raises(ValueError, match="requires conditions and result rules"):
        _evaluate(policy=_policy(rules=()))
    rules = (
        EligibilityResultRule(
            StatusExpression(condition.condition_id, ConditionStatus.SATISFIED),
            OpportunityStatus.ELIGIBLE,
        ),
        EligibilityResultRule(
            StatusExpression(condition.condition_id, ConditionStatus.SATISFIED),
            OpportunityStatus.INELIGIBLE,
        ),
    )
    with pytest.raises(ValueError, match="exactly one deterministic"):
        _evaluate(policy=_policy(rules=rules))
    with pytest.raises(ValueError, match="outer whitespace"):
        BusinessOpportunityEvaluator().evaluate(
            _forecast(uuid.uuid4()),
            _policy(),
            assessment_time=_time(),
            opportunity_type=" growth",
            canonical_subject="subject",
        )


def test_repeated_evaluation_is_deterministic_and_models_are_immutable() -> None:
    first = _evaluate()
    second = _evaluate()
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.status = OpportunityStatus.UNAVAILABLE  # type: ignore[misc]
