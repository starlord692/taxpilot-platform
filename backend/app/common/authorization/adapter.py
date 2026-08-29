"""Platform Authority adapter over Business Administration owner attestation."""

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.common.authorization.contracts import (
    OwnerAuthorizationDecision,
    ProtectedOwnerOperation,
)


@runtime_checkable
class BusinessAdministrationOwnerAttestation(Protocol):
    """Business Administration seam retained behind Platform Authority."""

    async def is_owner(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether a user has an active owner membership."""
        ...


@dataclass(frozen=True, slots=True)
class BusinessAdministrationOwnerAuthorizationAdapter:
    """Publish owner authorization without exposing membership persistence."""

    owner_attestation: BusinessAdministrationOwnerAttestation

    async def authorize_owner_operation(
        self,
        *,
        actor_id: uuid.UUID,
        business_id: uuid.UUID,
        operation: ProtectedOwnerOperation,
    ) -> OwnerAuthorizationDecision:
        """Return the owner decision for the approved protected operation."""
        _ = operation
        is_authorized = await self.owner_attestation.is_owner(
            business_id=business_id,
            user_id=actor_id,
        )
        return OwnerAuthorizationDecision(is_authorized=is_authorized)
