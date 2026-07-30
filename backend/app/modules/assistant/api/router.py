"""Assistant API router."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.responses import SuccessResponse
from app.modules.assistant.api.dependencies import (
    get_assistant_service,
    get_assistant_trust_service,
)
from app.modules.assistant.schemas import (
    AssistantConversationResponse,
    AssistantMessageRequest,
    AssistantResponse,
)
from app.modules.assistant.services import AssistantService
from app.modules.assistant.trust import (
    AssistantConversationAudit,
    AssistantRunExplanation,
    AssistantTrustService,
)
from app.modules.identity.dependencies.current_user import CurrentUser

router = APIRouter(prefix="/assistant", tags=["Assistant"])
BusinessIdQuery = Annotated[
    uuid.UUID,
    Query(description="Business context used to validate conversation access."),
]


@router.post(
    "/messages",
    response_model=SuccessResponse[AssistantResponse],
    status_code=status.HTTP_200_OK,
    summary="Send a message to the assistant",
    description=(
        "Processes a user message through the assistant orchestrator. Business "
        "facts are grounded only through approved tools and validated business context."
    ),
)
async def send_assistant_message(
    request: AssistantMessageRequest,
    current_user: CurrentUser,
    assistant_service: Annotated[AssistantService, Depends(get_assistant_service)],
) -> SuccessResponse[AssistantResponse]:
    """Send a user message to the assistant orchestration service."""
    response = await assistant_service.send_message(
        request=request,
        current_user=current_user,
    )
    return SuccessResponse(
        success=True,
        message="Assistant response generated",
        data=response,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=SuccessResponse[AssistantConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get an assistant conversation",
    description=(
        "Returns a conversation only inside the authenticated business context."
    ),
)
async def get_assistant_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    assistant_service: Annotated[AssistantService, Depends(get_assistant_service)],
    business_id: BusinessIdQuery,
) -> SuccessResponse[AssistantConversationResponse]:
    """Return one business-scoped assistant conversation."""
    response = await assistant_service.get_conversation(
        conversation_id=conversation_id,
        business_id=business_id,
        current_user=current_user,
    )
    return SuccessResponse(
        success=True,
        message="Assistant conversation retrieved",
        data=response,
    )

@router.get(
    "/runs/{run_id}/explanation",
    response_model=SuccessResponse[AssistantRunExplanation],
    status_code=status.HTTP_200_OK,
    summary="Explain an assistant run",
    description=(
        "Returns a read-only trust report for one assistant run, including "
        "policy decisions, approval traces, tool execution, evidence, grounding, "
        "and trust score metadata."
    ),
)
async def explain_assistant_run(
    run_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    trust_service: Annotated[
        AssistantTrustService,
        Depends(get_assistant_trust_service),
    ],
    business_id: BusinessIdQuery,
) -> SuccessResponse[AssistantRunExplanation]:
    """Return a read-only assistant run explanation."""
    response = await trust_service.explain_run(
        business_id=business_id,
        conversation_id=conversation_id,
        run_id=run_id,
        current_user=current_user,
    )
    return SuccessResponse(
        success=True,
        message="Assistant run explanation generated",
        data=response,
    )


@router.get(
    "/conversations/{conversation_id}/audit",
    response_model=SuccessResponse[AssistantConversationAudit],
    status_code=status.HTTP_200_OK,
    summary="Audit an assistant conversation",
    description=(
        "Returns a read-only chronological audit of assistant messages, runs, "
        "execution plans, tool calls, approvals, and context snapshots."
    ),
)
async def audit_assistant_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    trust_service: Annotated[
        AssistantTrustService,
        Depends(get_assistant_trust_service),
    ],
    business_id: BusinessIdQuery,
) -> SuccessResponse[AssistantConversationAudit]:
    """Return a read-only assistant conversation audit."""
    response = await trust_service.audit_conversation(
        business_id=business_id,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    return SuccessResponse(
        success=True,
        message="Assistant conversation audit generated",
        data=response,
    )