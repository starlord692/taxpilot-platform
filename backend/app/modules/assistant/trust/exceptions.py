"""Assistant trust exceptions."""

from app.modules.assistant.exceptions import AssistantConversationNotFoundException


class AssistantRunNotFoundException(AssistantConversationNotFoundException):
    """Raised when a run cannot be found in the current assistant context."""

    error_code = "assistant.run_not_found"
