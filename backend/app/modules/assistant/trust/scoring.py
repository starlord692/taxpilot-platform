"""Trust scoring for assistant explainability reports."""


from app.modules.assistant.trust.schemas import (
    AssistantTrustScore,
    TrustGrade,
    TrustPolicyResult,
    TrustPolicyStatus,
)

LOW_TRUST_THRESHOLD = 0.7
MEDIUM_TRUST_THRESHOLD = 0.9


class AssistantTrustScorer:
    """Calculate structural trust scores from evaluated trust policies."""

    def score(self, policy_results: list[TrustPolicyResult]) -> AssistantTrustScore:
        """Return an advisory structural trust score."""
        failed = sum(
            result.status == TrustPolicyStatus.FAIL for result in policy_results
        )
        warnings = sum(
            result.status == TrustPolicyStatus.WARNING for result in policy_results
        )
        passed = sum(
            result.status == TrustPolicyStatus.PASS for result in policy_results
        )
        applicable = passed + warnings + failed
        if applicable == 0:
            score = 1.0
        else:
            score = max(0.0, (passed + (warnings * 0.5)) / applicable)
        grade = TrustGrade.HIGH
        if score < LOW_TRUST_THRESHOLD:
            grade = TrustGrade.LOW
        elif score < MEDIUM_TRUST_THRESHOLD:
            grade = TrustGrade.MEDIUM
        limitations = [
            "Trust score is structural and does not prove every natural-language "
            "sentence semantically correct."
        ]
        return AssistantTrustScore(
            score=round(score, 2),
            grade=grade,
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            limitations=limitations,
        )
