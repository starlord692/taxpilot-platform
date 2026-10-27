"""Dependencies for Momentum API router."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.accounting.financial_performance_evidence.adapters import (
    BusinessMembershipAuthorizationAdapter,
    InMemoryMonetaryConfigurationAdapter,
)
from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMaterialityDetermination,
    AccountingMonetaryConfiguration,
    AccountingPolicyContext,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    MaterialityPort,
)
from app.modules.accounting.financial_performance_evidence.repository import (
    SQLAlchemyFinancialEffectsAdapter,
    SQLAlchemyHistoricalEvidenceAdapter,
    SQLAlchemyObservationPeriodAdapter,
)
from app.modules.accounting.financial_performance_evidence.service import (
    AccountingFinancialPerformanceEvidenceProvider,
)
from app.modules.business.repository.membership import BusinessMembershipRepository
from app.modules.momentum.service import (
    AFPEProviderPort,
    FinancialPerformanceMomentumService,
)


class DefaultMaterialityAdapter:
    """Default Accounting materiality adapter evaluating field-level materiality."""

    def determine(
        self,
        *,
        field: str,
        value: Decimal,
        currency: str,
    ) -> AccountingMaterialityDetermination:
        return AccountingMaterialityDetermination(
            outcome="MATERIAL" if value != Decimal("0") else "NOT_MATERIAL",
            materiality_policy_id="ACCOUNTING-MATERIALITY-POLICY",
            materiality_policy_version="1.0",
            basis="ACCOUNTING_GOVERNED_DEFAULT",
        )


def get_afpe_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AFPEProviderPort:
    """Construct production AFPE provider backed by repository adapters."""
    policy = AccountingPolicyContext(
        accounting_policy_id="AFPE-POLICY-PRODUCTION",
        accounting_policy_version="1.2",
        period_policy_id="ACCOUNTING-PERIOD-POLICY",
        period_policy_version="1.0",
        materiality_policy_id="ACCOUNTING-MATERIALITY-POLICY",
        materiality_policy_version="1.0",
    )

    auth_adapter = BusinessMembershipAuthorizationAdapter(
        memberships=BusinessMembershipRepository(session)
    )
    obs_adapter = SQLAlchemyObservationPeriodAdapter(
        session,
        supported_granularities=frozenset({"MONTHLY", "QUARTERLY", "ANNUAL"}),
    )
    effects_adapter = SQLAlchemyFinancialEffectsAdapter(session)
    historical_adapter = SQLAlchemyHistoricalEvidenceAdapter(session)
    materiality_adapter: MaterialityPort = DefaultMaterialityAdapter()
    monetary_adapter = InMemoryMonetaryConfigurationAdapter(
        (
            AccountingMonetaryConfiguration(
                currency="USD",
                scale=2,
                rounding_mode="ROUND_HALF_EVEN",
            ),
            AccountingMonetaryConfiguration(
                currency="INR",
                scale=2,
                rounding_mode="ROUND_HALF_EVEN",
            ),
        )
    )

    return AccountingFinancialPerformanceEvidenceProvider(
        authorization=auth_adapter,
        periods=obs_adapter,
        financial_effects=effects_adapter,
        materiality=materiality_adapter,
        historical=historical_adapter,
        monetary=monetary_adapter,
        policy_context=policy,
        clock=lambda: datetime.now(UTC),
    )


def get_momentum_service(
    afpe_provider: Annotated[AFPEProviderPort, Depends(get_afpe_provider)],
) -> FinancialPerformanceMomentumService:
    """Provide production FinancialPerformanceMomentumService instance."""
    return FinancialPerformanceMomentumService(afpe_provider=afpe_provider)
