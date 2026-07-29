"""Versioned prompt construction for assistant runs."""

from pathlib import Path

from app.modules.assistant.context.schemas import ConversationContext
from app.modules.assistant.memory.policies import MAX_CONTEXT_BLOCK_CHARS
from app.modules.assistant.providers.schemas import LLMMessage
from app.modules.assistant.schemas.requests import AssistantMessageRequest

PROMPT_VERSION = "assistant-context-v1"
_PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptBuilder:
    """Build versioned assistant prompts from checked-in prompt files."""

    prompt_version = PROMPT_VERSION

    def build_messages(
        self,
        *,
        request: AssistantMessageRequest,
        history: list[LLMMessage],
        context: ConversationContext | None = None,
    ) -> list[LLMMessage]:
        """Build provider-neutral messages for one assistant run."""
        system_prompt = self._read_prompt("system_v1.md")
        grounding_prompt = self._read_prompt("grounded_response_v1.md")
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="system", content=grounding_prompt),
        ]
        if context is not None:
            messages.append(
                LLMMessage(
                    role="system",
                    content=context.to_prompt_block(max_chars=MAX_CONTEXT_BLOCK_CHARS),
                )
            )
        messages.extend(history)
        messages.append(LLMMessage(role="user", content=request.message))
        return messages

    def _read_prompt(self, filename: str) -> str:
        """Read a checked-in prompt by filename."""
        return (_PROMPT_DIR / filename).read_text(encoding="utf-8").strip()
