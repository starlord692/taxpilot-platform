"""Technology-neutral Platform Authority owner-authorization contract."""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProtectedOwnerOperation(StrEnum):
    """The single Founder-approved protected owner operation."""

    BUSINESS_GOAL_ESTABLISH_OR_CONFIRM = "BUSINESS_GOAL_ESTABLISH_OR_CONFIRM"


@dataclass(frozen=True, slots=True)
class OwnerAuthorizationDecision:
    """The authoritative owner-authorization outcome without extra metadata."""

    is_authorized: bool


@runtime_checkable
class OwnerAuthorizationContract(Protocol):
    """Published Platform Authority boundary for owner authorization."""

    async def authorize_owner_operation(
        self,
        *,
        actor_id: uuid.UUID,
        business_id: uuid.UUID,
        operation: ProtectedOwnerOperation,
    ) -> OwnerAuthorizationDecision:
        """Return the authoritative owner-authorization decision."""
        ...
