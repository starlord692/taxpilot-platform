"""Pure deterministic policy evaluation and publication for Business Season."""

import uuid
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.modules.business_season.models import (
    BUSINESS_SEASON_NAMESPACE,
    BusinessSeason,
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionKind,
    SeasonAuthoritativeInput,
    SeasonConditionEvaluation,
    SeasonEvaluationContext,
    SeasonLifecycle,
    SeasonPolicy,
    SeasonStatus,
    SeasonTraceability,
    SemanticInputReference,
    UnavailableSeasonInformation,
    valid_value,
)


class BusinessSeasonService:
    """Assemble, evaluate, and explicitly publish immutable Season artifacts."""

    def evaluate(
        self,
        *,
        context: SeasonEvaluationContext,
        policy: SeasonPolicy,
        season_type: str,
        canonical_subject: str,
        season_version: str,
        effective_from: datetime,
        effective_until: datetime | None,
    ) -> BusinessSeason:
        self._identity_components(season_type, canonical_subject, season_version)
        if effective_until is not None and effective_until <= effective_from:
            raise ValueError("season effective period is invalid")
        serialized = "|".join(
            (str(context.business_id), season_type, canonical_subject, season_version)
        )
        if context.assessment_time < effective_from or (
            effective_until is not None and context.assessment_time >= effective_until
        ):
            return self._season(
                context,
                policy,
                season_type,
                canonical_subject,
                season_version,
                effective_from,
                effective_until,
                uuid.uuid5(BUSINESS_SEASON_NAMESPACE, serialized),
                SeasonStatus.INACTIVE,
                (),
                (),
                (),
            )
        evaluations: list[SeasonConditionEvaluation] = []
        unavailable: list[UnavailableSeasonInformation] = []
        for rule in policy.result_rules:
            evaluation, details = self._condition(rule.condition, context, policy)
            evaluations.append(evaluation)
            unavailable.extend(details)
            if evaluation.status is SeasonStatus.ACTIVE or (
                evaluation.status is SeasonStatus.UNAVAILABLE
                and rule.outcome is SeasonStatus.UNAVAILABLE
            ):
                return self._season(
                    context,
                    policy,
                    season_type,
                    canonical_subject,
                    season_version,
                    effective_from,
                    effective_until,
                    uuid.uuid5(BUSINESS_SEASON_NAMESPACE, serialized),
                    rule.outcome,
                    tuple(evaluations),
                    tuple(unavailable),
                    self._selected_inputs(tuple(evaluations), context),
                )
        return self._season(
            context,
            policy,
            season_type,
            canonical_subject,
            season_version,
            effective_from,
            effective_until,
            uuid.uuid5(BUSINESS_SEASON_NAMESPACE, serialized),
            SeasonStatus.UNAVAILABLE,
            tuple(evaluations),
            tuple(unavailable),
            self._selected_inputs(tuple(evaluations), context),
        )

    def publish(
        self,
        *,
        draft: BusinessSeason,
        published_at: datetime,
        history: tuple[BusinessSeason, ...],
    ) -> BusinessSeason:
        if draft.lifecycle is not SeasonLifecycle.DRAFT:
            raise ValueError("only a draft Season can be published")
        if any(
            item.lifecycle is SeasonLifecycle.PUBLISHED
            and item.season_id == draft.season_id
            for item in history
        ):
            raise ValueError("published Season identity and version conflict")
        return replace(
            draft, lifecycle=SeasonLifecycle.PUBLISHED, published_at=published_at
        )

    def _season(
        self,
        context: SeasonEvaluationContext,
        policy: SeasonPolicy,
        season_type: str,
        canonical_subject: str,
        season_version: str,
        effective_from: datetime,
        effective_until: datetime | None,
        season_id: uuid.UUID,
        status: SeasonStatus,
        evaluations: tuple[SeasonConditionEvaluation, ...],
        unavailable: tuple[UnavailableSeasonInformation, ...],
        selected: tuple[SeasonAuthoritativeInput, ...],
    ) -> BusinessSeason:
        references = tuple(item.condition_reference for item in selected)
        trace = SeasonTraceability(
            policy.policy_id,
            policy.version,
            policy.provenance,
            selected,
            evaluations,
        )
        limitations = context.limitations + tuple(item.reason for item in unavailable)
        return BusinessSeason(
            season_id,
            context.business_id,
            season_type,
            canonical_subject,
            season_version,
            status,
            context.assessment_time,
            effective_from,
            effective_until,
            policy.policy_id,
            policy.version,
            SeasonLifecycle.DRAFT,
            references,
            selected,
            limitations,
            selected,
            context.provenance,
            context.temporal_context,
            trace,
            unavailable,
        )

    def _condition(
        self,
        expression: ConditionExpression,
        context: SeasonEvaluationContext,
        policy: SeasonPolicy,
    ) -> tuple[SeasonConditionEvaluation, tuple[UnavailableSeasonInformation, ...]]:
        if expression.comparison is not None:
            return self._comparison(
                expression.condition_id, expression.comparison, context, policy
            )
        children = tuple(
            self._condition(child, context, policy)
            for child in (expression.all or expression.any or expression.not_ or ())
        )
        evaluations = tuple(item[0] for item in children)
        unavailable = tuple(detail for _, details in children for detail in details)
        statuses = tuple(item.status for item in evaluations)
        if expression.not_ is not None:
            status = {
                SeasonStatus.ACTIVE: SeasonStatus.INACTIVE,
                SeasonStatus.INACTIVE: SeasonStatus.ACTIVE,
                SeasonStatus.UNAVAILABLE: SeasonStatus.UNAVAILABLE,
            }[statuses[0]]
            kind = ConditionKind.NOT
        elif expression.all is not None:
            status = (
                SeasonStatus.INACTIVE
                if SeasonStatus.INACTIVE in statuses
                else SeasonStatus.ACTIVE
                if all(value is SeasonStatus.ACTIVE for value in statuses)
                else SeasonStatus.UNAVAILABLE
            )
            kind = ConditionKind.ALL
        else:
            status = (
                SeasonStatus.ACTIVE
                if SeasonStatus.ACTIVE in statuses
                else SeasonStatus.INACTIVE
                if all(value is SeasonStatus.INACTIVE for value in statuses)
                else SeasonStatus.UNAVAILABLE
            )
            kind = ConditionKind.ANY
        return SeasonConditionEvaluation(
            expression.condition_id, kind, status, children=evaluations
        ), unavailable

    def _comparison(
        self,
        condition_id: str,
        comparison: Comparison,
        context: SeasonEvaluationContext,
        policy: SeasonPolicy,
    ) -> tuple[SeasonConditionEvaluation, tuple[UnavailableSeasonInformation, ...]]:
        input_, unavailable = self._resolve(comparison.input, context, policy)
        if input_ is None:
            return (
                SeasonConditionEvaluation(
                    condition_id,
                    ConditionKind.COMPARISON,
                    SeasonStatus.UNAVAILABLE,
                    operator=comparison.operator,
                    operand=comparison.operand,
                ),
                unavailable,
            )
        if not valid_value(input_.value, input_.value_type, input_.enum_vocabulary):
            detail = UnavailableSeasonInformation(
                input_.source,
                input_.capability,
                input_.reference_id,
                input_.field,
                "authoritative input has an invalid declared value type",
            )
            return (
                SeasonConditionEvaluation(
                    condition_id,
                    ConditionKind.COMPARISON,
                    SeasonStatus.UNAVAILABLE,
                    input_.condition_reference,
                    comparison.operator,
                    comparison.operand,
                ),
                (detail,),
            )
        status = self._compare(input_.value, comparison)
        return (
            SeasonConditionEvaluation(
                condition_id,
                ConditionKind.COMPARISON,
                status,
                input_.condition_reference,
                comparison.operator,
                comparison.operand,
            ),
            (),
        )

    def _resolve(
        self,
        semantic: SemanticInputReference,
        context: SeasonEvaluationContext,
        policy: SeasonPolicy,
    ) -> tuple[
        SeasonAuthoritativeInput | None, tuple[UnavailableSeasonInformation, ...]
    ]:
        matches = tuple(
            item for item in context.inputs if item.semantic_input == semantic
        )
        precedence = next(
            (
                item
                for item in policy.source_precedence
                if item.semantic_input == semantic
            ),
            None,
        )
        sources = (
            precedence.sources
            if precedence is not None
            else tuple(dict.fromkeys(item.source for item in matches))
        )
        if len(sources) != 1 and precedence is None:
            return None, (
                self._missing(semantic, "multiple sources require declared precedence"),
            )
        for source in sources:
            candidates = tuple(item for item in matches if item.source == source)
            if len(candidates) == 1 and valid_value(
                candidates[0].value,
                candidates[0].value_type,
                candidates[0].enum_vocabulary,
            ):
                return candidates[0], ()
        return None, (
            self._missing(
                semantic, "no declared source provides a valid authoritative input"
            ),
        )

    @staticmethod
    def _missing(
        semantic: SemanticInputReference, reason: str
    ) -> UnavailableSeasonInformation:
        return UnavailableSeasonInformation(
            "unresolved", semantic.capability, "unresolved", semantic.field, reason
        )

    @staticmethod
    def _compare(value: Any, comparison: Comparison) -> SeasonStatus:
        operand = comparison.operand.value
        try:
            if comparison.operator is ComparisonOperator.EQUALS:
                matched = value == operand
            elif comparison.operator is ComparisonOperator.NOT_EQUALS:
                matched = value != operand
            elif comparison.operator is ComparisonOperator.GREATER_THAN:
                matched = value > operand
            elif comparison.operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
                matched = value >= operand
            elif comparison.operator is ComparisonOperator.LESS_THAN:
                matched = value < operand
            elif comparison.operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
                matched = value <= operand
            elif comparison.operator is ComparisonOperator.CONTAINS:
                matched = operand in value
            else:
                matched = value in operand
        except TypeError:
            return SeasonStatus.UNAVAILABLE
        return SeasonStatus.ACTIVE if matched else SeasonStatus.INACTIVE

    @staticmethod
    def _selected_inputs(
        evaluations: tuple[SeasonConditionEvaluation, ...],
        context: SeasonEvaluationContext,
    ) -> tuple[SeasonAuthoritativeInput, ...]:
        references = tuple(
            item.input_reference
            for evaluation in evaluations
            for item in BusinessSeasonService._walk(evaluation)
            if item.input_reference is not None
        )
        return tuple(
            input_
            for reference in references
            for input_ in context.inputs
            if input_.condition_reference == reference
        )

    @staticmethod
    def _walk(
        evaluation: SeasonConditionEvaluation,
    ) -> tuple[SeasonConditionEvaluation, ...]:
        return (evaluation,) + tuple(
            descendant
            for child in evaluation.children
            for descendant in BusinessSeasonService._walk(child)
        )

    @staticmethod
    def _identity_components(*components: str) -> None:
        if not all(
            component.strip() and component == component.strip()
            for component in components
        ):
            raise ValueError("season identity components must be non-blank and trimmed")
