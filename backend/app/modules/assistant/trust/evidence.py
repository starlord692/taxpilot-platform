"""Evidence-chain builder for assistant trust reports."""

from datetime import datetime
from typing import Any, cast

from app.modules.assistant.models import AssistantToolCall, ToolCallStatus
from app.modules.assistant.trust.schemas import (
    AssistantEvidenceChain,
    AssistantEvidenceReference,
)


class AssistantEvidenceChainBuilder:
    """Build structural evidence chains from completed tool outputs."""

    def build(self, tool_calls: list[AssistantToolCall]) -> AssistantEvidenceChain:
        """Return available authoritative evidence from assistant tool calls."""
        references: list[AssistantEvidenceReference] = []
        completed_outputs = 0
        for tool_call in tool_calls:
            if (
                tool_call.status != ToolCallStatus.COMPLETED
                or tool_call.output_payload is None
            ):
                continue
            completed_outputs += 1
            references.append(
                AssistantEvidenceReference(
                    source_type="assistant_tool_output",
                    source_id=str(tool_call.id),
                    source_label=tool_call.tool_name,
                    tool_name=tool_call.tool_name,
                    generated_at=tool_call.completed_at,
                )
            )
            references.extend(self._extract_insight_evidence(tool_call))
        limitations = []
        if not references:
            limitations.append("No completed authoritative tool output was available.")
        return AssistantEvidenceChain(
            evidence=references,
            authoritative_tool_outputs=completed_outputs,
            limitations=limitations,
        )

    def _extract_insight_evidence(
        self,
        tool_call: AssistantToolCall,
    ) -> list[AssistantEvidenceReference]:
        """Extract AI-004 insight evidence references when present."""
        payload = tool_call.output_payload or {}
        result = payload.get("result")
        if not isinstance(result, dict):
            return []
        raw_evidence = result.get("evidence")
        if not isinstance(raw_evidence, list):
            return []
        references: list[AssistantEvidenceReference] = []
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            generated_at = self._parse_datetime(item.get("generated_at"))
            references.append(
                AssistantEvidenceReference(
                    source_type=str(item.get("source_type", "insight_evidence")),
                    source_id=(
                        str(item["source_id"]) if item.get("source_id") else None
                    ),
                    source_label=str(item.get("source_label", tool_call.tool_name)),
                    tool_name=tool_call.tool_name,
                    metric=str(item["metric"]) if item.get("metric") else None,
                    value=cast(Any, item.get("value")),
                    generated_at=generated_at,
                )
            )
        return references

    def _parse_datetime(self, value: object) -> datetime | None:
        """Parse a serialized datetime from tool output when available."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None
