"""Tests for AI-002 assistant business memory and context intelligence."""

import uuid
from collections.abc import Callable
from typing import cast

import pytest

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.context import ConversationContextBuilder
from app.modules.assistant.memory import ConversationSummarizer
from app.modules.assistant.models import (
    AssistantMessage,
    AssistantRunStatus,
    AssistantWorkflowStatus,
    AssistantWorkflowType,
    EntityResolutionConfidence,
    MessageRole,
)
from app.modules.assistant.providers import MockAssistantProvider
from app.modules.assistant.resolution import EntityResolver
from app.modules.assistant.schemas import AssistantMessageRequest
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import AssistantToolRegistry, GetBusinessContextTool
from app.modules.assistant.workflow import WorkflowTracker
from tests.test_assistant_core import (
    FakeAssistantConversationRepository,
    FakeAssistantUnitOfWork,
    build_business,
    build_identity_user,
    build_membership,
)


def test_entity_resolver_extracts_explicit_invoice_reference() -> None:
    """Entity resolution stores provenance and confidence for explicit references."""
    entity_id = uuid.uuid4()
    source_id = uuid.uuid4()
    result = EntityResolver().extract_entity_reference(
        message=f"Please review invoice {entity_id}",
        source_id=source_id,
    )

    assert result is not None
    assert result.entity_type == "invoice"
    assert result.entity_id == entity_id
    assert result.confidence == EntityResolutionConfidence.HIGH
    assert result.provenance.source == "user_message"
    assert result.provenance.source_id == str(source_id)


def test_workflow_tracker_detects_sales_invoice_waiting_state() -> None:
    """Workflow tracking uses deterministic rules and has expiration metadata."""
    transition = WorkflowTracker().build_transition(
        message="Which invoice should I issue?",
        active_entity_refs=[],
    )

    assert transition.workflow_type == AssistantWorkflowType.SALES_INVOICE
    assert transition.status == AssistantWorkflowStatus.WAITING_FOR_USER
    assert transition.pending_decisions[0]["decision"] == "clarify_user_intent"
    assert transition.provenance["generated_by"] == "WorkflowTracker"


def test_prompt_builder_includes_context_before_current_request() -> None:
    """Prompt context is inserted as system context before the user message."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    context = ConversationContextBuilder().build(
        business_context=__import__(
            "app.modules.business.api.context",
            fromlist=["BusinessContext"],
        ).BusinessContext(business=business, membership=membership, user=user),
        conversation_id=conversation_id,
        language="en",
        timezone="Asia/Calcutta",
        summary="Current task: review invoice.",
        active_workflow=None,
        active_entities=[],
        recent_tool_calls=[],
    )

    messages = PromptBuilder().build_messages(
        request=AssistantMessageRequest(
            business_id=business_id,
            message="Continue this invoice task.",
        ),
        history=[],
        context=context,
    )

    assert messages[-1].role == "user"
    assert "TaxPilot conversation context follows" in messages[2].content
    assert "review invoice" in messages[2].content


def test_conversation_summarizer_is_conversation_scoped() -> None:
    """Summaries are deterministic and limited to the current conversation."""
    conversation = __import__(
        "app.modules.assistant.models",
        fromlist=["AssistantConversation"],
    ).AssistantConversation(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Invoice help",
        language="en",
        timezone="Asia/Calcutta",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    messages = [
        AssistantMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT,
            content=f"Message {index}",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        for index in range(8)
    ]

    summary = ConversationSummarizer().summarize(
        conversation=conversation,
        messages=messages,
    )

    assert summary is not None
    assert summary.startswith("assistant-summary-v1")
    assert "Scope: current conversation only" in summary


@pytest.mark.asyncio
async def test_assistant_service_records_context_snapshot_and_workflow() -> None:
    """Assistant orchestration records context intelligence without ERP writes."""
    user_id = uuid.uuid4()
    business_id = uuid.uuid4()
    user = build_identity_user(user_id)
    business = build_business(business_id)
    membership = build_membership(business_id=business_id, user_id=user_id)
    repository = FakeAssistantConversationRepository()
    uow = FakeAssistantUnitOfWork(
        business=business,
        membership=membership,
        assistant_conversations=repository,
    )
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    service = AssistantService(
        unit_of_work_factory=cast(Callable[[], AssistantUnitOfWork], lambda: uow),
        event_dispatcher=EventDispatcher(),
        provider=MockAssistantProvider(),
        tool_registry=registry,
        prompt_builder=PromptBuilder(),
    )

    response = await service.send_message(
        request=AssistantMessageRequest(
            business_id=business_id,
            message="Help me with this invoice",
        ),
        current_user=user,
    )

    assert response.run.status == AssistantRunStatus.COMPLETED
    assert response.run.prompt_version == "assistant-context-v1"
    assert repository.context_snapshots
    assert repository.context_snapshots[0].provenance["source"] == "system_derived"
    assert repository.entity_references[0].entity_type == "invoice"
    assert repository.workflows[0].workflow_type == AssistantWorkflowType.SALES_INVOICE
    assert repository.workflows[0].expires_at > utc_now()
