"""Assistant action provenance helpers."""

import uuid

from app.modules.assistant.actions.schemas import ACTION_PROVENANCE_VERSION
from app.modules.business.api.context import BusinessContext


class ActionProvenanceBuilder:
    """Build provenance for action drafts and controlled execution."""

    def for_draft(
        self,
        *,
        business_context: BusinessContext,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
        action_type: str,
        source: str,
        manifest_version: str,
        capability_version: str,
    ) -> dict[str, object]:
        """Return provenance for one assistant action draft."""
        return {
            "provenance_version": ACTION_PROVENANCE_VERSION,
            "business_id": str(business_context.business_id),
            "user_id": str(business_context.user_id),
            "conversation_id": str(conversation_id),
            "run_id": str(run_id),
            "action_type": action_type,
            "source": source,
            "manifest_version": manifest_version,
            "capability_version": capability_version,
            "authority": "assistant_action_service",
        }
