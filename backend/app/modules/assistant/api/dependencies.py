"""Assistant API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.assistant.providers import AssistantProvider, MockAssistantProvider
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import AssistantToolRegistry, GetBusinessContextTool


def get_session_factory() -> Callable[[], AsyncSession]:
    """Return the configured async session factory."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    return database_state.session_factory


def get_event_dispatcher() -> EventDispatcher:
    """Provide an event dispatcher instance."""
    return EventDispatcher()


def get_assistant_provider() -> AssistantProvider:
    """Provide the configured assistant model provider."""
    return MockAssistantProvider()


def get_tool_registry() -> AssistantToolRegistry:
    """Provide the assistant tool registry."""
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    return registry


def get_assistant_service() -> AssistantService:
    """Provide the assistant orchestration service."""
    session_factory = get_session_factory()
    unit_of_work_factory = cast(
        Callable[[], AssistantUnitOfWork],
        lambda: SQLAlchemyUnitOfWork(session_factory),
    )
    return AssistantService(
        unit_of_work_factory=unit_of_work_factory,
        event_dispatcher=get_event_dispatcher(),
        provider=get_assistant_provider(),
        tool_registry=get_tool_registry(),
        prompt_builder=PromptBuilder(),
    )
