"""Reusable business-context fakes for API tests."""

import uuid

from app.modules.business.models import (
    Business,
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)


class FakeBusinessRepository:
    """Fake business repository returning active businesses by default."""

    def __init__(
        self,
        *,
        missing_business_ids: set[uuid.UUID] | None = None,
        status: BusinessStatus = BusinessStatus.ACTIVE,
    ) -> None:
        """Initialize fake business lookup behavior."""
        self.missing_business_ids = missing_business_ids or set()
        self.status = status

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return an active business unless configured as missing."""
        if business_id in self.missing_business_ids:
            return None
        return Business(
            id=business_id,
            legal_name="TaxPilot Test Business",
            business_type=BusinessType.PRIVATE_LIMITED,
            registration_status=RegistrationStatus.REGISTERED,
            status=self.status,
        )
