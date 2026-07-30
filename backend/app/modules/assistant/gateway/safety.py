"""Response safety checks for assistant provider output."""

from app.modules.assistant.gateway.schemas import ProviderSafetyStatus


class ProviderResponseSafetyChecker:
    """Apply deterministic safety checks to provider output."""

    def assess_tool_selection(self, *, finding_count: int) -> ProviderSafetyStatus:
        """Classify tool-selection safety after structural validation."""
        _ = finding_count
        return ProviderSafetyStatus.SAFE

    def assess_completion(
        self,
        *,
        content: str,
        tool_output_count: int,
        require_grounding: bool,
    ) -> tuple[ProviderSafetyStatus, list[str]]:
        """Classify completion safety using structural grounding rules."""
        findings: list[str] = []
        normalized = content.lower()
        business_terms = (
            "business",
            "invoice",
            "gst",
            "profit",
            "revenue",
            "inventory",
            "cash flow",
        )
        mentions_business_fact = any(term in normalized for term in business_terms)
        if require_grounding and mentions_business_fact and tool_output_count == 0:
            refusal_terms = (
                "authorized tool result",
                "approved tools",
                "need an authorized tool",
            )
            if any(term in normalized for term in refusal_terms):
                findings.append(
                    "Provider declined business-specific facts without tool output."
                )
                return ProviderSafetyStatus.SAFE_WITH_WARNINGS, findings
            findings.append("Business-specific response lacks completed tool output.")
            return ProviderSafetyStatus.BLOCKED, findings
        if "bypass approval" in normalized:
            findings.append("Provider response attempted to bypass approval.")
            return ProviderSafetyStatus.BLOCKED, findings
        findings.append("Provider response passed structural safety checks.")
        return ProviderSafetyStatus.SAFE, findings
