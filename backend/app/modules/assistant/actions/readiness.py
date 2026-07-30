"""Execution readiness validation for assistant actions."""

from app.modules.assistant.actions.capabilities import ActionCapabilityRegistry
from app.modules.assistant.actions.enums import (
    ActionReadinessStatus,
    AssistantActionType,
    ReadinessSeverity,
)
from app.modules.assistant.actions.manifests import ActionManifestRegistry
from app.modules.assistant.actions.schemas import ReadinessFinding
from app.modules.business.api.context import BusinessContext


class ExecutionReadinessValidator:
    """Validate action drafts before approval and execution."""

    def __init__(
        self,
        *,
        manifests: ActionManifestRegistry | None = None,
        capabilities: ActionCapabilityRegistry | None = None,
    ) -> None:
        """Initialize with canonical registries."""
        self._manifests = manifests or ActionManifestRegistry()
        self._capabilities = capabilities or ActionCapabilityRegistry()

    def validate(
        self,
        *,
        action_type: AssistantActionType,
        draft_payload: dict[str, object],
        business_context: BusinessContext | None,
    ) -> tuple[ActionReadinessStatus, list[ReadinessFinding], dict[str, object] | None]:
        """Validate one action draft payload and context."""
        findings: list[ReadinessFinding] = []
        if business_context is None:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.ERROR,
                    code="assistant.action.business_context_required",
                    message="A validated business context is required.",
                    blocking=True,
                )
            )
            return ActionReadinessStatus.BLOCKED, findings, None

        if not self._manifests.supports(action_type):
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.ERROR,
                    code="assistant.action.unsupported",
                    message="The requested assistant action is not supported.",
                    field="action_type",
                    blocking=True,
                )
            )
            return ActionReadinessStatus.BLOCKED, findings, None

        manifest = self._manifests.get(action_type)
        capability = self._capabilities.get(manifest.action_type)
        if not capability.supports_approval_gate or not capability.supports_idempotency:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.ERROR,
                    code="assistant.action.capability_incomplete",
                    message=(
                        "The action capability is not safe for controlled execution."
                    ),
                    blocking=True,
                )
            )

        if not draft_payload:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.ERROR,
                    code="assistant.action.payload_required",
                    message="Draft payload is required before approval.",
                    field="draft_payload",
                    blocking=True,
                )
            )
        else:
            findings.append(
                ReadinessFinding(
                    severity=ReadinessSeverity.INFO,
                    code="assistant.action.payload_present",
                    message="Draft payload is present and ready for domain validation.",
                    blocking=False,
                )
            )

        status = (
            ActionReadinessStatus.BLOCKED
            if any(finding.blocking for finding in findings)
            else ActionReadinessStatus.NEEDS_APPROVAL
        )
        validated_payload = (
            None if status == ActionReadinessStatus.BLOCKED else draft_payload
        )
        return status, findings, validated_payload
