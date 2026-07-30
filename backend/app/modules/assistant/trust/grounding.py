"""Grounding verification for assistant trust reports."""

from app.modules.assistant.models import AssistantRunStatus, AssistantToolCall
from app.modules.assistant.trust.schemas import (
    AssistantEvidenceChain,
    AssistantGroundingReport,
    GroundingStatus,
)


class AssistantGroundingVerifier:
    """Perform structural grounding checks against persisted tool outputs."""

    def verify(
        self,
        *,
        run_status: AssistantRunStatus,
        tool_calls: list[AssistantToolCall],
        evidence_chain: AssistantEvidenceChain,
    ) -> AssistantGroundingReport:
        """Return the structural grounding classification for a run."""
        findings: list[str] = []
        limitations = [
            "Grounding verification checks available tool evidence; it is not a "
            "semantic proof of every assistant sentence."
        ]
        completed_outputs = evidence_chain.authoritative_tool_outputs
        evidence_count = len(evidence_chain.evidence)
        if run_status == AssistantRunStatus.FAILED:
            findings.append(
                "Assistant run failed before a grounded response completed."
            )
            return AssistantGroundingReport(
                status=GroundingStatus.NOT_APPLICABLE,
                grounded_tool_outputs=completed_outputs,
                evidence_count=evidence_count,
                findings=findings,
                limitations=limitations,
            )
        if not tool_calls:
            findings.append("No assistant tool calls were recorded for this run.")
            return AssistantGroundingReport(
                status=GroundingStatus.UNGROUNDED,
                grounded_tool_outputs=0,
                evidence_count=0,
                findings=findings,
                limitations=limitations,
            )
        if completed_outputs == 0:
            findings.append("Tool calls exist, but none completed with output.")
            return AssistantGroundingReport(
                status=GroundingStatus.UNGROUNDED,
                grounded_tool_outputs=0,
                evidence_count=evidence_count,
                findings=findings,
                limitations=limitations,
            )
        if evidence_count <= completed_outputs:
            findings.append("Completed tool outputs are available for grounding.")
            status = GroundingStatus.PARTIALLY_GROUNDED
        else:
            findings.append(
                "Completed tool outputs and evidence references are available."
            )
            status = GroundingStatus.GROUNDED
        return AssistantGroundingReport(
            status=status,
            grounded_tool_outputs=completed_outputs,
            evidence_count=evidence_count,
            findings=findings,
            limitations=limitations,
        )
