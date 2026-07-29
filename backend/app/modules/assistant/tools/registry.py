"""Assistant tool registry."""

from app.modules.assistant.exceptions import AssistantToolNotFoundException
from app.modules.assistant.tools.base import AssistantTool, ToolDefinition


class AssistantToolRegistry:
    """Registry of permissioned tools available to the assistant."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, AssistantTool] = {}

    def register(self, tool: AssistantTool) -> None:
        """Register or replace an assistant tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> AssistantTool:
        """Return a registered tool by name."""
        tool = self._tools.get(name)
        if tool is None:
            raise AssistantToolNotFoundException(
                "Assistant tool is not registered",
                details={"tool_name": name},
            )
        return tool

    def definitions(self) -> list[ToolDefinition]:
        """Return provider-facing metadata for all registered tools."""
        return [tool.definition() for tool in self._tools.values()]
