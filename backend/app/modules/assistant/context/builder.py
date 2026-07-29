"""Conversation context builder for assistant prompt intelligence."""

import uuid

from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.context.schemas import (
    ActiveEntityContext,
    ContextProvenance,
    ConversationContext,
    ToolOutputContext,
    WorkflowContext,
)
from app.modules.assistant.memory.policies import CONTEXT_VERSION
from app.modules.assistant.models import (
    AssistantEntityReference,
    AssistantToolCall,
    AssistantWorkflow,
    ContextSource,
)
from app.modules.business.api.context import BusinessContext


class ConversationContextBuilder:
    """Build deterministic conversation-scoped assistant context."""

    context_version = CONTEXT_VERSION

    def build(
        self,
        *,
        business_context: BusinessContext,
        conversation_id: uuid.UUID,
        language: str,
        timezone: str,
        summary: str | None,
        active_workflow: AssistantWorkflow | None,
        active_entities: list[AssistantEntityReference],
        recent_tool_calls: list[AssistantToolCall],
    ) -> ConversationContext:
        """Build a complete context snapshot for one assistant run."""
        business = business_context.business
        membership = business_context.membership
        provenance = ContextProvenance(
            source=ContextSource.SYSTEM_DERIVED.value,
            source_id=str(conversation_id),
            source_version=self.context_version,
            generated_by="ConversationContextBuilder",
            generated_at=utc_now(),
        )
        workflow_context = (
            self._workflow_context(active_workflow) if active_workflow else None
        )
        return ConversationContext(
            context_version=self.context_version,
            business_id=business_context.business_id,
            user_id=business_context.user_id,
            conversation_id=conversation_id,
            language=language,
            timezone=timezone,
            business_context={
                "business_id": str(business.id),
                "business_code": business.business_code,
                "legal_name": business.legal_name,
                "status": business.status.value,
                "membership_role": membership.role,
                "provenance": ContextProvenance(
                    source=ContextSource.BUSINESS_CONTEXT.value,
                    source_id=str(business.id),
                    source_version="business-context-v1",
                    generated_by="resolve_business_context",
                    generated_at=utc_now(),
                ).model_dump(mode="json"),
            },
            conversation_summary=summary,
            active_workflow=workflow_context,
            active_entities=[
                self._entity_context(entity) for entity in active_entities
            ],
            recent_tool_outputs=[
                self._tool_output_context(tool_call) for tool_call in recent_tool_calls
            ],
            pending_decisions=(
                workflow_context.pending_decisions if workflow_context else []
            ),
            provenance=provenance,
        )

    def _entity_context(
        self,
        reference: AssistantEntityReference,
    ) -> ActiveEntityContext:
        """Convert a stored entity reference into prompt context."""
        provenance = ContextProvenance.model_validate(reference.provenance)
        return ActiveEntityContext(
            entity_type=reference.entity_type,
            entity_id=reference.entity_id,
            entity_label=reference.entity_label,
            confidence=reference.confidence,
            confidence_score=float(reference.confidence_score),
            provenance=provenance,
        )

    def _tool_output_context(self, tool_call: AssistantToolCall) -> ToolOutputContext:
        """Convert a completed tool call into prompt context."""
        output = tool_call.output_payload or {}
        result = output.get("result")
        if not isinstance(result, dict):
            result = {}
        return ToolOutputContext(
            tool_name=tool_call.tool_name,
            result=result,
            provenance=ContextProvenance(
                source=ContextSource.TOOL_OUTPUT.value,
                source_id=str(tool_call.id),
                source_version="assistant-tool-output-v1",
                generated_by="AssistantToolExecutor",
                generated_at=tool_call.completed_at or utc_now(),
            ),
        )

    def _workflow_context(self, workflow: AssistantWorkflow) -> WorkflowContext:
        """Convert a stored workflow into prompt context."""
        provenance = ContextProvenance.model_validate(workflow.provenance)
        return WorkflowContext(
            workflow_type=workflow.workflow_type,
            status=workflow.status,
            current_step=workflow.current_step,
            active_entity_refs=workflow.active_entity_refs,
            pending_decisions=workflow.pending_decisions,
            expires_at=workflow.expires_at,
            provenance=provenance,
        )

