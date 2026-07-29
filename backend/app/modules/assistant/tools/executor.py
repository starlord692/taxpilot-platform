"""Permissioned assistant tool execution."""

from app.modules.assistant.exceptions import AssistantToolPermissionException
from app.modules.assistant.models import ToolSideEffect
from app.modules.assistant.tools.base import ToolContext, ToolResult
from app.modules.assistant.tools.registry import AssistantToolRegistry


class AssistantToolExecutor:
    """Validate permissions and execute registered assistant tools."""

    def __init__(self, registry: AssistantToolRegistry) -> None:
        """Initialize with a registered tool catalog."""
        self._registry = registry

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolContext,
        allow_write_tools: bool = False,
    ) -> ToolResult:
        """Execute one tool after validating context and side-effect policy."""
        tool = self._registry.get(tool_name)
        if tool.requires_business_context and context.business_context is None:
            raise AssistantToolPermissionException(
                "Assistant tool requires an authenticated business context",
                details={"tool_name": tool_name},
            )
        if tool.side_effect == ToolSideEffect.WRITE and not allow_write_tools:
            raise AssistantToolPermissionException(
                "Write-capable assistant tools are not enabled for this run",
                details={"tool_name": tool_name},
            )
        payload = tool.input_model.model_validate(arguments)
        return await tool.execute(payload, context)
