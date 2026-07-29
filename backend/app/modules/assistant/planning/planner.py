"""Deterministic assistant execution planner."""

import hashlib
import json

from app.modules.assistant.exceptions import AssistantToolNotFoundException
from app.modules.assistant.models import ExecutionMode
from app.modules.assistant.planning.schemas import (
    ExecutionPlan,
    ExecutionPlanStep,
    ToolCapabilityManifest,
)
from app.modules.assistant.providers import LLMToolCall
from app.modules.assistant.tools import AssistantToolRegistry


def normalized_hash(payload: object) -> str:
    """Return a stable hash for idempotency and provenance."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ExecutionPlanner:
    """Convert provider-proposed tool calls into versioned execution plans."""

    def __init__(self, registry: AssistantToolRegistry) -> None:
        """Initialize with the registered assistant tool catalog."""
        self._registry = registry

    def build_plan(
        self,
        *,
        selected_tools: list[LLMToolCall],
        prompt_version: str,
        context_version: str,
        business_id: str,
        conversation_id: str,
        run_id: str,
    ) -> ExecutionPlan:
        """Normalize selected tools into a deterministic execution plan."""
        steps: list[ExecutionPlanStep] = []
        for index, selected_tool in enumerate(selected_tools, start=1):
            tool = self._registry.get(selected_tool.tool_name)
            definition = tool.definition()
            if definition.capability_name is None:
                definition.capability_name = definition.name
            manifest = ToolCapabilityManifest.model_validate(definition.model_dump())
            step_seed = {
                "business_id": business_id,
                "conversation_id": conversation_id,
                "run_id": run_id,
                "tool_name": selected_tool.tool_name,
                "arguments": selected_tool.arguments,
                "step_order": index,
            }
            steps.append(
                ExecutionPlanStep(
                    step_order=index,
                    tool_name=selected_tool.tool_name,
                    arguments=selected_tool.arguments,
                    dependencies=[],
                    manifest=manifest,
                    idempotency_key=normalized_hash(step_seed),
                )
            )
        execution_mode = self._execution_mode(steps)
        plan_seed = {
            "business_id": business_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "steps": [step.model_dump(mode="json") for step in steps],
        }
        return ExecutionPlan(
            prompt_version=prompt_version,
            context_version=context_version,
            execution_mode=execution_mode,
            idempotency_key=normalized_hash(plan_seed),
            steps=steps,
        )

    def validate_structure(self, plan: ExecutionPlan) -> None:
        """Reject invalid execution structures before policy evaluation."""
        seen_orders: set[int] = set()
        for step in plan.steps:
            if step.step_order in seen_orders:
                raise ValueError("Execution plan contains duplicate step order")
            seen_orders.add(step.step_order)
            try:
                self._registry.get(step.tool_name)
            except AssistantToolNotFoundException:
                raise
            if step.step_order in step.dependencies:
                raise ValueError("Execution step cannot depend on itself")

    def _execution_mode(self, steps: list[ExecutionPlanStep]) -> ExecutionMode:
        """Return the safest supported execution mode for the step collection."""
        if len(steps) <= 1:
            return ExecutionMode.SINGLE
        if all(step.manifest.side_effect.value == "read" for step in steps):
            return ExecutionMode.PARALLEL_READ_ONLY
        return ExecutionMode.SEQUENTIAL
