"""Focused acceptance tests for frozen deterministic Business Season v1.0."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import pytest

from app.modules.business_season.models import (
    BUSINESS_SEASON_NAMESPACE,
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionOperand,
    SeasonAuthoritativeInput,
    SeasonEvaluationContext,
    SeasonLifecycle,
    SeasonPolicy,
    SeasonResultRule,
    SeasonStatus,
    SemanticInputReference,
    SourcePrecedence,
    ValueType,
)
from app.modules.business_season.service import BusinessSeasonService


class State(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


def _time() -> datetime:
    return datetime(2026, 8, 19, tzinfo=UTC)


def _semantic(
    field: str = "state", type_: ValueType = ValueType.ENUM
) -> SemanticInputReference:
    return SemanticInputReference("Business DNA", field, type_)


def _input(
    *,
    source: str = "BusinessDNA",
    field: str = "state",
    value: object = State.OPEN,
    type_: ValueType = ValueType.ENUM,
    reference_id: str = "dna-state-1",
) -> SeasonAuthoritativeInput:
    return SeasonAuthoritativeInput(
        source,
        "Business DNA",
        reference_id,
        field,
        type_,
        value,
        (State.OPEN, State.CLOSED) if type_ is ValueType.ENUM else (),
    )


def _condition(
    condition_id: str = "is-open",
    *,
    field: str = "state",
    value: object = State.OPEN,
    type_: ValueType = ValueType.ENUM,
    operator: ComparisonOperator = ComparisonOperator.EQUALS,
) -> ConditionExpression:
    operand = (value,) if operator is ComparisonOperator.IN else value
    operand_type = ValueType.STRING if type_ is ValueType.TEXT else type_
    return ConditionExpression(
        condition_id,
        comparison=Comparison(
            _semantic(field, type_), operator, ConditionOperand(operand_type, operand)
        ),
    )


def _policy(
    condition: ConditionExpression | None = None,
    *,
    precedence: tuple[SourcePrecedence, ...] = (),
) -> SeasonPolicy:
    expression = condition or _condition()
    return SeasonPolicy(
        "season-policy",
        "1.0",
        (
            SeasonResultRule("active", expression, SeasonStatus.ACTIVE),
            SeasonResultRule(
                "inactive",
                ConditionExpression("not-open", not_=(expression,)),
                SeasonStatus.INACTIVE,
            ),
            SeasonResultRule("unavailable", expression, SeasonStatus.UNAVAILABLE),
        ),
        "founder-approved",
        precedence,
    )


def _context(
    inputs: tuple[SeasonAuthoritativeInput, ...] = (),
) -> SeasonEvaluationContext:
    return SeasonEvaluationContext(
        uuid.UUID("12345678-1234-5678-1234-567812345678"),
        _time(),
        inputs or (_input(),),
        "owner-published",
        _time(),
        ("source limit",),
    )


def _evaluate(
    *,
    context: SeasonEvaluationContext | None = None,
    policy: SeasonPolicy | None = None,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
):
    return BusinessSeasonService().evaluate(
        context=context or _context(),
        policy=policy or _policy(),
        season_type="filing",
        canonical_subject="GST",
        season_version="1",
        effective_from=effective_from or _time(),
        effective_until=effective_until,
    )


def test_identity_status_traceability_and_determinism() -> None:
    first = _evaluate()
    second = _evaluate()
    serialized = "12345678-1234-5678-1234-567812345678|filing|GST|1"
    assert first.status is SeasonStatus.ACTIVE
    assert first.season_id == uuid.uuid5(BUSINESS_SEASON_NAMESPACE, serialized)
    assert first.identity_serialization == serialized
    assert first == second
    assert first.evidence[0].reference_id == "dna-state-1"
    assert first.lifecycle is SeasonLifecycle.DRAFT


def test_effective_period_precedes_policy_evaluation() -> None:
    season = _evaluate(effective_from=_time() + timedelta(days=1))
    assert season.status is SeasonStatus.INACTIVE
    assert not season.traceability.condition_evaluations


def test_ordered_first_match_and_no_match_unavailable() -> None:
    condition = _condition()
    policy = SeasonPolicy(
        "p",
        "1",
        (
            SeasonResultRule("first", condition, SeasonStatus.INACTIVE),
            SeasonResultRule("later", condition, SeasonStatus.ACTIVE),
        ),
        "founder",
    )
    assert _evaluate(policy=policy).status is SeasonStatus.INACTIVE
    unmatched = _policy(_condition(value=State.CLOSED))
    assert _evaluate(policy=unmatched).status is SeasonStatus.INACTIVE


def test_three_valued_all_any_not_and_unavailable_traceability() -> None:
    active = _condition("open")
    missing = _condition("missing", field="missing")
    all_ = ConditionExpression("all", all=(active, missing))
    any_ = ConditionExpression("any", any=(active, missing))
    not_ = ConditionExpression("not", not_=(missing,))
    service = BusinessSeasonService()
    for expression, expected in (
        (all_, SeasonStatus.UNAVAILABLE),
        (any_, SeasonStatus.ACTIVE),
        (not_, SeasonStatus.UNAVAILABLE),
    ):
        evaluation, unavailable = service._condition(expression, _context(), _policy())
        assert evaluation.status is expected
        if expected is SeasonStatus.UNAVAILABLE:
            assert unavailable[0].field == "missing"


def test_contains_and_in_follow_frozen_rules() -> None:
    text_input = _input(field="notice", value="Annual GST filing", type_=ValueType.TEXT)
    contains = _condition(
        field="notice",
        value="GST",
        type_=ValueType.TEXT,
        operator=ComparisonOperator.CONTAINS,
    )
    assert (
        _evaluate(context=_context((text_input,)), policy=_policy(contains)).status
        is SeasonStatus.ACTIVE
    )
    in_expression = _condition(operator=ComparisonOperator.IN)
    assert _evaluate(policy=_policy(in_expression)).status is SeasonStatus.ACTIVE
    with pytest.raises(ValueError, match="contains"):
        _condition(
            type_=ValueType.INTEGER, value=1, operator=ComparisonOperator.CONTAINS
        )
    with pytest.raises(ValueError, match="operand value"):
        _condition(type_=ValueType.INTEGER, value="1")


@pytest.mark.parametrize(
    ("operator", "value", "operand", "value_type"),
    (
        (ComparisonOperator.EQUALS, State.OPEN, State.OPEN, ValueType.ENUM),
        (ComparisonOperator.NOT_EQUALS, State.CLOSED, State.OPEN, ValueType.ENUM),
        (ComparisonOperator.GREATER_THAN, 2, 1, ValueType.INTEGER),
        (ComparisonOperator.GREATER_THAN_OR_EQUAL, 2, 2, ValueType.INTEGER),
        (ComparisonOperator.LESS_THAN, 1, 2, ValueType.INTEGER),
        (ComparisonOperator.LESS_THAN_OR_EQUAL, 2, 2, ValueType.INTEGER),
        (
            ComparisonOperator.CONTAINS,
            "GST filing",
            "GST",
            ValueType.STRING,
        ),
        (ComparisonOperator.IN, State.OPEN, State.OPEN, ValueType.ENUM),
    ),
)
def test_every_approved_comparison_operator_is_deterministic(
    operator: ComparisonOperator,
    value: object,
    operand: object,
    value_type: ValueType,
) -> None:
    condition = _condition(
        value=operand,
        type_=value_type,
        operator=operator,
    )
    input_ = _input(value=value, type_=value_type)
    assert (
        _evaluate(context=_context((input_,)), policy=_policy(condition)).status
        is SeasonStatus.ACTIVE
    )


def test_source_precedence_selects_declared_valid_source_only() -> None:
    first = _input(source="first", value=State.CLOSED, reference_id="first-id")
    second = _input(source="second", value=State.OPEN, reference_id="second-id")
    precedence = SourcePrecedence(_semantic(), ("second", "first"))
    season = _evaluate(
        context=_context((first, second)), policy=_policy(precedence=(precedence,))
    )
    assert season.status is SeasonStatus.ACTIVE
    assert season.source_references[0].source == "second"
    unavailable = _evaluate(context=_context((first, second)))
    assert unavailable.status is SeasonStatus.UNAVAILABLE
    assert (
        unavailable.unavailable_information[0].reason
        == "multiple sources require declared precedence"
    )


def test_publication_preserves_history_and_rejects_identity_conflict() -> None:
    draft = _evaluate()
    published = BusinessSeasonService().publish(
        draft=draft, published_at=_time(), history=()
    )
    assert published.lifecycle is SeasonLifecycle.PUBLISHED
    assert draft.lifecycle is SeasonLifecycle.DRAFT
    with pytest.raises(ValueError, match="identity and version conflict"):
        BusinessSeasonService().publish(
            draft=draft, published_at=_time(), history=(published,)
        )


def test_business_isolation_and_immutability() -> None:
    context = _context()
    other = SeasonEvaluationContext(
        uuid.uuid4(), _time(), context.inputs, "owner", _time()
    )
    assert _evaluate(context=other).business_id == other.business_id
    with pytest.raises(FrozenInstanceError):
        _evaluate().status = SeasonStatus.UNAVAILABLE  # type: ignore[misc]
