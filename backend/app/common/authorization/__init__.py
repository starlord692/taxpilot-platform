"""Platform-level, technology-neutral authorization boundaries."""

from app.common.authorization.contracts import (
    OwnerAuthorizationContract,
    OwnerAuthorizationDecision,
    ProtectedOwnerOperation,
)

__all__ = [
    "OwnerAuthorizationContract",
    "OwnerAuthorizationDecision",
    "ProtectedOwnerOperation",
]
