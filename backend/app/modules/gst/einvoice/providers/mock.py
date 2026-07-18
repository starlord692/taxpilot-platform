"""Mock GST provider used by tests and local development."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.gst.einvoice.providers.interface import GSTProviderClient


class MockGSTProvider(GSTProviderClient):
    """Deterministic provider adapter that never calls external systems."""

    provider_name = "mock"

    async def authenticate(self) -> dict[str, Any]:
        """Return a mock authentication token."""
        return {"authenticated": True, "provider": self.provider_name}

    async def generate_irn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate deterministic IRN payload from invoice data."""
        await self.authenticate()
        invoice_id = str(payload["invoice_id"])
        digest = hashlib.sha256(invoice_id.encode()).hexdigest()
        now = datetime.now(tz=UTC)
        irn = digest[:64].upper()
        return {
            "irn": irn,
            "ack_number": f"ACK-{digest[:12].upper()}",
            "ack_date": now,
            "qr_content": f"IRN:{irn}|INV:{invoice_id}",
            "qr_hash": digest,
            "provider_name": self.provider_name,
            "raw": {"status": "generated", "provider": self.provider_name},
        }

    async def cancel_irn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return deterministic IRN cancellation response."""
        await self.authenticate()
        return {
            "cancelled": True,
            "cancelled_at": datetime.now(tz=UTC),
            "irn": payload["irn"],
            "raw": {"status": "cancelled", "provider": self.provider_name},
        }

    async def generate_eway_bill(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate deterministic e-way bill payload."""
        await self.authenticate()
        invoice_id = str(payload["invoice_id"])
        digest = hashlib.sha256(f"eway:{invoice_id}".encode()).hexdigest()
        now = datetime.now(tz=UTC)
        return {
            "eway_bill_number": f"EWB{digest[:12].upper()}",
            "valid_from": now,
            "valid_to": now + timedelta(days=1),
            "vehicle_number": payload.get("vehicle_number"),
            "transport_mode": payload["transport_mode"],
            "raw": {"status": "generated", "provider": self.provider_name},
        }

    async def cancel_eway_bill(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return deterministic e-way bill cancellation response."""
        await self.authenticate()
        return {
            "cancelled": True,
            "cancelled_at": datetime.now(tz=UTC),
            "eway_bill_number": payload["eway_bill_number"],
            "raw": {"status": "cancelled", "provider": self.provider_name},
        }

    async def get_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return deterministic provider status."""
        await self.authenticate()
        return {
            "provider": self.provider_name,
            "invoice_id": str(payload["invoice_id"]),
            "status": "available",
        }
