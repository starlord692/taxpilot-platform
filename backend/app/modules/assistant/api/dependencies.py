"""Assistant API dependencies."""

from collections.abc import Callable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.events import EventDispatcher
from app.common.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import database_state, initialize_database
from app.modules.accounting.financial_statements.services import (
    FinancialStatementService,
)
from app.modules.accounting.financial_statements.services.statement_service import (
    FinancialStatementUnitOfWork,
)
from app.modules.accounting.trial_balance.services import TrialBalanceService
from app.modules.accounting.trial_balance.services.trial_balance_service import (
    TrialBalanceUnitOfWork,
)
from app.modules.assistant.insights import (
    BusinessInsightService,
    GenerateBusinessInsightsTool,
)
from app.modules.assistant.providers import AssistantProvider, MockAssistantProvider
from app.modules.assistant.services import AssistantService, PromptBuilder
from app.modules.assistant.services.assistant_service import AssistantUnitOfWork
from app.modules.assistant.tools import AssistantToolRegistry, GetBusinessContextTool
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.gst.compliance.services.compliance_service import (
    GSTComplianceUnitOfWork,
)
from app.modules.inventory.services import InventoryService
from app.modules.inventory.services.inventory_service import InventoryUnitOfWork


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


def get_business_insight_service() -> BusinessInsightService:
    """Provide the read-only business insight service."""
    session_factory = get_session_factory()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(session_factory)

    return BusinessInsightService(
        financial_statement_service=FinancialStatementService(
            unit_of_work_factory=cast(
                Callable[[], FinancialStatementUnitOfWork],
                uow_factory,
            )
        ),
        trial_balance_service=TrialBalanceService(
            unit_of_work_factory=cast(
                Callable[[], TrialBalanceUnitOfWork],
                uow_factory,
            )
        ),
        gst_compliance_service=GSTComplianceService(
            unit_of_work_factory=cast(
                Callable[[], GSTComplianceUnitOfWork],
                uow_factory,
            ),
            event_dispatcher=get_event_dispatcher(),
        ),
        inventory_service=InventoryService(
            unit_of_work_factory=cast(
                Callable[[], InventoryUnitOfWork],
                uow_factory,
            )
        ),
        event_dispatcher=get_event_dispatcher(),
    )


def get_tool_registry() -> AssistantToolRegistry:
    """Provide the assistant tool registry."""
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    registry.register(GenerateBusinessInsightsTool(get_business_insight_service()))
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
