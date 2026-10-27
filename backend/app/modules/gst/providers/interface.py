"""Provider interface for GSTIN registration verification under TAX-01."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GSTINProviderResponse:
    """Standardized response from an external or mock GSTIN verification provider.

    NOTE: A provider response is a raw observation from a verification adapter.
    It does NOT directly constitute a stored evidence record or authorized invoice
    issuance evidence until ingested and validated by the persistence and service layer.
    """

    gstin: str
    is_found: bool
    status: str | None
    legal_name: str | None = None
    trade_name: str | None = None
    state_code: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    raw_payload_hash: str | None = None
    evidence_source: str = "UNKNOWN_PROVIDER"
    observed_at: datetime | None = None


class GSTINVerificationProvider(ABC):
    """Abstract interface for GSTIN verification providers (GSP, NIC, Mock)."""

    @abstractmethod
    async def verify_gstin(self, gstin: str) -> GSTINProviderResponse:
        """Query verification details for a GSTIN.

        Must operate deterministically and strictly offline in mock mode.
        Must not make live network calls in Milestone 1.
        """
