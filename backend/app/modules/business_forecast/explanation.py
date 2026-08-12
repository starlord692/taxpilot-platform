"""Deterministic structured explanations for completed Forecast evaluations."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.business_forecast.models import PublishedForecast
from app.modules.business_forecast.policy import (
    ApplicabilityOutcome,
    ConditionInputReference,
    ConditionStatus,
    EvaluationImpact,
    PolicyConditionResult,
    PolicyEvaluation,
)

FORECAST_005_EXPLANATION_NAMESPACE = uuid.UUID("18e4c106-7679-5fa7-a86d-40f0e2fa6380")


class ExplanationFactType(StrEnum):
    CONDITION_STATUS = "condition_status"
    CONDITION_APPLICABILITY = "condition_applicability"
    CONDITION_UNAVAILABLE = "condition_unavailable"


@dataclass(frozen=True, slots=True)
class ExplanationFact:
    fact_type: ExplanationFactType
    condition_id: str
    status: ConditionStatus | ApplicabilityOutcome
    evaluation_impact: EvaluationImpact | None = None


@dataclass(frozen=True, slots=True)
class UnavailableInformation:
    condition_id: str
    input_reference: ConditionInputReference | None
    condition_status: ConditionStatus
    evaluation_impact: EvaluationImpact

    def __post_init__(self) -> None:
        if self.condition_status is not ConditionStatus.UNAVAILABLE:
            raise ValueError("unavailable information requires unavailable status")


@dataclass(frozen=True, slots=True)
class ExplanationSummary:
    overall_status: ConditionStatus
    satisfied_condition_ids: tuple[str, ...]
    not_satisfied_condition_ids: tuple[str, ...]
    not_applicable_condition_ids: tuple[str, ...]
    unavailable_condition_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionExplanation:
    condition_id: str
    status: ConditionStatus
    applicability: ApplicabilityOutcome
    explanation_facts: tuple[ExplanationFact, ...]
    evidence_references: tuple[ConditionInputReference, ...]
    unavailable_information: tuple[UnavailableInformation, ...]


@dataclass(frozen=True, slots=True)
class ForecastExplanation:
    explanation_id: uuid.UUID
    evaluation_id: str
    forecast_identity: PublishedForecast
    overall_status: ConditionStatus
    summary: ExplanationSummary
    condition_explanations: tuple[ConditionExplanation, ...]
    evidence_references: tuple[str, ...]
    limitation_references: tuple[str, ...]
    unavailable_information: tuple[UnavailableInformation, ...]
    policy_provenance: str
    policy_version: str
    policy_effective_from: datetime
    policy_effective_until: datetime | None
    generated_at: datetime


class BusinessForecastExplanationEngine:
    """Preserve, validate, and structure authoritative PolicyEvaluation facts."""

    def explain(self, evaluation: PolicyEvaluation) -> ForecastExplanation:
        self._validate(evaluation)
        condition_explanations = tuple(
            self._condition_explanation(result)
            for result in evaluation.condition_results
        )
        unavailable = tuple(
            item
            for explanation in condition_explanations
            for item in explanation.unavailable_information
        )
        summary = self._summary(evaluation)
        return ForecastExplanation(
            explanation_id=uuid.uuid5(
                FORECAST_005_EXPLANATION_NAMESPACE,
                evaluation.evaluation_id,
            ),
            evaluation_id=evaluation.evaluation_id,
            forecast_identity=evaluation.forecast_identity,
            overall_status=evaluation.overall_status,
            summary=summary,
            condition_explanations=condition_explanations,
            evidence_references=evaluation.traceability,
            limitation_references=tuple(
                forecast_limitation.reference
                for source in evaluation.forecast_traceability.source_references
                for forecast_limitation in source.limitations
            )
            + evaluation.limitations,
            unavailable_information=unavailable,
            policy_provenance=evaluation.policy_provenance,
            policy_version=evaluation.policy_version,
            policy_effective_from=evaluation.policy_effective_from,
            policy_effective_until=evaluation.policy_effective_until,
            generated_at=evaluation.evaluation_time,
        )

    def _validate(self, evaluation: PolicyEvaluation) -> None:
        if not evaluation.evaluation_id.strip():
            raise ValueError("policy evaluation identity must not be blank")
        forecast = evaluation.forecast_identity
        if not isinstance(forecast, PublishedForecast):
            raise ValueError("policy evaluation requires authoritative forecast")
        if forecast.forecast.identity.business_id != evaluation.business_id:
            raise ValueError("evaluation business must match forecast")
        if evaluation.evaluation_context.business_id != evaluation.business_id:
            raise ValueError("evaluation context business must match evaluation")
        result_ids = tuple(
            result.condition_id for result in evaluation.condition_results
        )
        if not result_ids or len(result_ids) != len(set(result_ids)):
            raise ValueError("evaluation condition results must be unique and present")
        if not evaluation.policy_provenance.strip() or not evaluation.traceability:
            raise ValueError(
                "evaluation traceability and policy provenance are required"
            )

    def _condition_explanation(
        self, condition: PolicyConditionResult
    ) -> ConditionExplanation:
        facts = [
            ExplanationFact(
                ExplanationFactType.CONDITION_STATUS,
                condition.condition_id,
                condition.status,
            ),
            ExplanationFact(
                ExplanationFactType.CONDITION_APPLICABILITY,
                condition.condition_id,
                condition.applicability,
            ),
        ]
        unavailable: tuple[UnavailableInformation, ...] = ()
        if condition.status is ConditionStatus.UNAVAILABLE:
            facts.append(
                ExplanationFact(
                    ExplanationFactType.CONDITION_UNAVAILABLE,
                    condition.condition_id,
                    condition.status,
                    condition.evaluation_impact,
                )
            )
            input_reference = (
                condition.unavailable_input_references[0]
                if len(condition.unavailable_input_references) == 1
                else None
            )
            unavailable = (
                UnavailableInformation(
                    condition.condition_id,
                    input_reference,
                    condition.status,
                    condition.evaluation_impact,
                ),
            )
        return ConditionExplanation(
            condition.condition_id,
            condition.status,
            condition.applicability,
            tuple(facts),
            condition.authoritative_references,
            unavailable,
        )

    def _summary(self, evaluation: PolicyEvaluation) -> ExplanationSummary:
        by_status = {
            status: tuple(
                result.condition_id
                for result in evaluation.condition_results
                if result.status is status
            )
            for status in ConditionStatus
        }
        return ExplanationSummary(
            evaluation.overall_status,
            by_status[ConditionStatus.SATISFIED],
            by_status[ConditionStatus.NOT_SATISFIED],
            by_status[ConditionStatus.NOT_APPLICABLE],
            by_status[ConditionStatus.UNAVAILABLE],
        )
