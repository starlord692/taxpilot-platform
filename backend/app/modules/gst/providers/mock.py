"""Deterministic offline mock GSTIN verification provider.

IMPORTANT: This mock provider produces simulated offline test data only.
It does NOT connect to the GSTN, NIC, or any GST Suvidha Provider, and its
outputs do NOT certify actual legal or active registration status with government
tax authorities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.modules.gst.providers.interface import (
    GSTINProviderResponse,
    GSTINVerificationProvider,
)
from app.modules.gst.schemas.validators import validate_gstin


class MockGSTINVerificationProvider(GSTINVerificationProvider):
    """Deterministic, offline mock provider for tests and local development."""

    provider_name: str = "OFFLINE_MOCK_VERIFIER"

    def __init__(
        self,
        *,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize mock provider with optional custom GSTIN overrides."""
        self._overrides: dict[str, dict[str, Any]] = overrides or {}

    def set_mock_status(
        self,
        gstin: str,
        *,
        status: str,
        legal_name: str | None = None,
        trade_name: str | None = None,
        is_found: bool = True,
    ) -> None:
        """Configure mock behavior for a specific GSTIN."""
        self._overrides[gstin] = {
            "status": status,
            "legal_name": legal_name or f"Mock Enterprise {gstin[:5]}",
            "trade_name": trade_name or f"Trading {gstin[:5]}",
            "is_found": is_found,
        }

    async def verify_gstin(self, gstin: str) -> GSTINProviderResponse:
        """Simulate verification offline deterministically without network calls."""
        # Validate format using standard regex validator
        normalized_gstin = validate_gstin(gstin)
        now = datetime.now(UTC)

        # Check explicit overrides
        if normalized_gstin in self._overrides:
            override = self._overrides[normalized_gstin]
            is_found = bool(override.get("is_found", True))
            status = override.get("status") if is_found else None
            legal_name = override.get("legal_name") if is_found else None
            trade_name = override.get("trade_name") if is_found else None

            raw_payload = {
                "gstin": normalized_gstin,
                "is_found": is_found,
                "status": status,
                "legal_name": legal_name,
                "trade_name": trade_name,
                "provider": self.provider_name,
                "simulated": True,
            }
            digest = hashlib.sha256(
                json.dumps(raw_payload, sort_keys=True).encode()
            ).hexdigest()

            return GSTINProviderResponse(
                gstin=normalized_gstin,
                is_found=is_found,
                status=status,
                legal_name=legal_name,
                trade_name=trade_name,
                state_code=normalized_gstin[:2],
                raw_payload=raw_payload,
                raw_payload_hash=digest,
                evidence_source=self.provider_name,
                observed_at=now,
            )

        # Built-in deterministic patterns for unconfigured GSTINs
        # Suffix conventions on valid 15-character GSTINs:
        # - ends with 'C': simulated Cancelled
        # - ends with '8': simulated Inactive
        # - ends with '0': simulated Not Found / Unregistered
        state_code = normalized_gstin[:2]
        is_cancelled = normalized_gstin.endswith("C")
        is_inactive = normalized_gstin.endswith("8")
        is_not_found = normalized_gstin.endswith("0")

        if is_not_found:
            raw_payload = {
                "gstin": normalized_gstin,
                "is_found": False,
                "error": "GSTIN_NOT_FOUND",
                "provider": self.provider_name,
                "simulated": True,
            }
            digest = hashlib.sha256(
                json.dumps(raw_payload, sort_keys=True).encode()
            ).hexdigest()
            return GSTINProviderResponse(
                gstin=normalized_gstin,
                is_found=False,
                status=None,
                raw_payload=raw_payload,
                raw_payload_hash=digest,
                evidence_source=self.provider_name,
                observed_at=now,
            )

        status = (
            "Cancelled" if is_cancelled else "Inactive" if is_inactive else "Active"
        )
        legal_name = f"Deterministic Mock Enterprise ({normalized_gstin})"
        trade_name = f"Mock Trade ({normalized_gstin})"

        raw_payload = {
            "gstin": normalized_gstin,
            "is_found": True,
            "status": status,
            "legal_name": legal_name,
            "trade_name": trade_name,
            "state_code": state_code,
            "provider": self.provider_name,
            "simulated": True,
        }
        digest = hashlib.sha256(
            json.dumps(raw_payload, sort_keys=True).encode()
        ).hexdigest()

        return GSTINProviderResponse(
            gstin=normalized_gstin,
            is_found=True,
            status=status,
            legal_name=legal_name,
            trade_name=trade_name,
            state_code=state_code,
            raw_payload=raw_payload,
            raw_payload_hash=digest,
            evidence_source=self.provider_name,
            observed_at=now,
        )
