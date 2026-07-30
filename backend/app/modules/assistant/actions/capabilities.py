"""Assistant action capability registry."""

from __future__ import annotations

from app.modules.assistant.actions.enums import AssistantActionType
from app.modules.assistant.actions.schemas import (
    ACTION_CAPABILITY_REGISTRY_VERSION,
    ActionCapability,
)


class ActionCapabilityRegistry:
    """Technical capabilities for supported assistant actions."""

    version = ACTION_CAPABILITY_REGISTRY_VERSION

    def __init__(self, capabilities: list[ActionCapability] | None = None) -> None:
        """Initialize default action capabilities."""
        configured = capabilities or [
            ActionCapability(
                action_type=action_type, adapter_name="DomainServiceActionAdapter"
            )
            for action_type in AssistantActionType
        ]
        self._capabilities = {
            capability.action_type: capability for capability in configured
        }

    def get(self, action_type: AssistantActionType) -> ActionCapability:
        """Return one action capability."""
        return self._capabilities[action_type]

    def list_capabilities(self) -> list[ActionCapability]:
        """Return all action capabilities."""
        return list(self._capabilities.values())
