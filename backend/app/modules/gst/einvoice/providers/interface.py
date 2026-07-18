"""Provider abstraction for GST e-invoicing integrations."""

from abc import ABC, abstractmethod
from typing import Any


class GSTProviderClient(ABC):
    """Abstract client implemented by GST Suvidha Provider adapters."""

    @abstractmethod
    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with the provider."""

    @abstractmethod
    async def generate_irn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate an invoice reference number."""

    @abstractmethod
    async def cancel_irn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel an invoice reference number."""

    @abstractmethod
    async def generate_eway_bill(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate an e-way bill."""

    @abstractmethod
    async def cancel_eway_bill(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel an e-way bill."""

    @abstractmethod
    async def get_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return provider status for an invoice."""
