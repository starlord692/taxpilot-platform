"""Deterministic conversation summarization for context intelligence."""

from app.modules.assistant.memory.policies import (
    SUMMARY_MESSAGE_THRESHOLD,
    SUMMARY_VERSION,
)
from app.modules.assistant.models import (
    AssistantConversation,
    AssistantMessage,
    MessageRole,
)


class ConversationSummarizer:
    """Build conversation-scoped summaries without long-term memory."""

    def should_summarize(self, messages: list[AssistantMessage]) -> bool:
        """Return whether the current conversation should refresh its summary."""
        return len(messages) >= SUMMARY_MESSAGE_THRESHOLD

    def summarize(
        self,
        *,
        conversation: AssistantConversation,
        messages: list[AssistantMessage],
    ) -> str | None:
        """Return an incremental deterministic summary for the current conversation."""
        if not self.should_summarize(messages):
            return conversation.summary
        user_messages = [
            message.content for message in messages if message.role == MessageRole.USER
        ]
        assistant_messages = [
            message.content
            for message in messages
            if message.role == MessageRole.ASSISTANT
        ]
        latest_user = (
            user_messages[-1] if user_messages else "No user request recorded."
        )
        latest_assistant = (
            assistant_messages[-1]
            if assistant_messages
            else "No assistant response recorded."
        )
        return (
            f"{SUMMARY_VERSION}: Current task: {latest_user[:240]}. "
            f"Latest assistant response: {latest_assistant[:240]}. "
            "Scope: current conversation only."
        )
