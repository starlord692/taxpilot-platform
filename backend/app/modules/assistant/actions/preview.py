"""Execution preview builder for assistant actions."""

from app.modules.assistant.actions.enums import ActionReadinessStatus
from app.modules.assistant.actions.schemas import (
    ActionManifest,
    ExecutionPreview,
    ReadinessFinding,
)


class ExecutionPreviewBuilder:
    """Build human-reviewable previews before approval and execution."""

    def build(
        self,
        *,
        manifest: ActionManifest,
        readiness_status: ActionReadinessStatus,
        readiness_findings: list[ReadinessFinding],
        idempotency_key: str,
    ) -> ExecutionPreview:
        """Return a preview for a pending assistant action."""
        return ExecutionPreview(
            action_type=manifest.action_type,
            summary=(
                f"Prepare {manifest.result_record_type} through "
                f"{manifest.required_service}."
            ),
            side_effect=manifest.side_effect,
            approval_required=manifest.approval_level.value != "none",
            approval_level=manifest.approval_level,
            downstream_integrations=manifest.downstream_integrations,
            readiness_status=readiness_status,
            readiness_findings=readiness_findings,
            idempotency_key=idempotency_key,
        )

