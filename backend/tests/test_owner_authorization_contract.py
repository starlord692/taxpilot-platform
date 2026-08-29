"""Focused tests for the Platform Authority owner-authorization contract."""

import uuid
from dataclasses import FrozenInstanceError, fields

import pytest

from app.common.authorization.adapter import (
    BusinessAdministrationOwnerAttestation,
    BusinessAdministrationOwnerAuthorizationAdapter,
)
from app.common.authorization.contracts import (
    OwnerAuthorizationContract,
    OwnerAuthorizationDecision,
    ProtectedOwnerOperation,
)


class OwnerAttestationFake:
    """In-memory Business Administration attestation seam."""

    def __init__(self, authorized: bool) -> None:
        self.authorized = authorized
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def is_owner(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        self.calls.append((business_id, user_id))
        return self.authorized


def _ids() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.UUID(int=1), uuid.UUID(int=2)


@pytest.mark.asyncio
async def test_owner_authorization_contract_returns_structured_allow_decision() -> None:
    business_id, actor_id = _ids()
    attestation = OwnerAttestationFake(True)
    adapter = BusinessAdministrationOwnerAuthorizationAdapter(attestation)

    decision = await adapter.authorize_owner_operation(
        actor_id=actor_id,
        business_id=business_id,
        operation=ProtectedOwnerOperation.BUSINESS_GOAL_ESTABLISH_OR_CONFIRM,
    )

    assert isinstance(adapter, OwnerAuthorizationContract)
    assert isinstance(attestation, BusinessAdministrationOwnerAttestation)
    assert decision == OwnerAuthorizationDecision(is_authorized=True)
    assert attestation.calls == [(business_id, actor_id)]


@pytest.mark.asyncio
async def test_owner_authorization_contract_returns_structured_denial_decision(
) -> None:
    business_id, actor_id = _ids()
    adapter = BusinessAdministrationOwnerAuthorizationAdapter(
        OwnerAttestationFake(False)
    )

    decision = await adapter.authorize_owner_operation(
        actor_id=actor_id,
        business_id=business_id,
        operation=ProtectedOwnerOperation.BUSINESS_GOAL_ESTABLISH_OR_CONFIRM,
    )

    assert decision == OwnerAuthorizationDecision(is_authorized=False)


def test_contract_is_limited_to_the_approved_operation_and_decision_shape() -> None:
    assert list(ProtectedOwnerOperation) == [
        ProtectedOwnerOperation.BUSINESS_GOAL_ESTABLISH_OR_CONFIRM
    ]
    assert tuple(field.name for field in fields(OwnerAuthorizationDecision)) == (
        "is_authorized",
    )


def test_authorization_decision_is_immutable() -> None:
    decision = OwnerAuthorizationDecision(is_authorized=True)

    with pytest.raises(FrozenInstanceError):
        decision.is_authorized = False
