"""Focused acceptance tests for frozen Business Goals v1.0."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

import app.modules.business_goals.service as business_goal_service
from app.common.authorization.contracts import OwnerAuthorizationDecision
from app.modules.business_goals.models import (
    BUSINESS_GOALS_NAMESPACE,
    BusinessGoal,
    GoalDeclaration,
    GoalDraftInput,
    GoalLifecycle,
    GoalProvenance,
    GoalProvenanceSourceType,
    GoalSupportingReference,
    GoalTemporalContext,
    UnavailableGoalInformation,
)
from app.modules.business_goals.ports import BusinessGoalReadProvider
from app.modules.business_goals.service import BusinessGoalService


class OwnerAuthorizationFake:
    """In-memory published Platform Authority authorization contract."""

    def __init__(self, authorized: bool) -> None:
        self.authorized = authorized
        self.calls: list[tuple[uuid.UUID, uuid.UUID, object]] = []

    async def authorize_owner_operation(
        self,
        *,
        actor_id: uuid.UUID,
        business_id: uuid.UUID,
        operation: object,
    ) -> OwnerAuthorizationDecision:
        self.calls.append((actor_id, business_id, operation))
        return OwnerAuthorizationDecision(is_authorized=self.authorized)


class GoalReadProviderFake:
    """In-memory owner-controlled read boundary."""

    async def get_current(
        self, *, business_id: uuid.UUID, context_time: datetime
    ) -> tuple[BusinessGoal, ...]:
        _ = business_id, context_time
        return ()

    async def get_history(
        self, *, business_id: uuid.UUID
    ) -> tuple[BusinessGoal, ...]:
        _ = business_id
        return ()


def _time() -> datetime:
    return datetime(2026, 8, 30, tzinfo=UTC)


def _ids() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.UUID(int=1), uuid.UUID(int=2)


def _draft(
    *,
    business_id: uuid.UUID | None = None,
    declarant_id: uuid.UUID | None = None,
    subject: str = "Open a second location",
    version: str = "1",
    effective_until: datetime | None = None,
) -> GoalDraftInput:
    default_business_id, default_declarant_id = _ids()
    return GoalDraftInput(
        business_id=business_id or default_business_id,
        canonical_subject=subject,
        goal_version=version,
        declaration=GoalDeclaration("Open a second location"),
        provenance=GoalProvenance(
            GoalProvenanceSourceType.OWNER,
            declarant_id or default_declarant_id,
            _time(),
        ),
        temporal_context=GoalTemporalContext(_time(), effective_until),
        evidence=(GoalSupportingReference("owner-evidence-1"),),
        limitations=("No target metric supplied.",),
        unavailable_information=(
            UnavailableGoalInformation("target metric", "not supplied"),
        ),
    )


async def _establish(
    draft: GoalDraftInput | None = None,
    authorization: OwnerAuthorizationFake | None = None,
) -> BusinessGoal:
    _, actor_id = _ids()
    return await BusinessGoalService().establish_draft(
        actor_id=actor_id,
        draft=draft or _draft(),
        authorization=authorization or OwnerAuthorizationFake(True),
    )


@pytest.mark.asyncio
async def test_identity_uses_exact_namespace_and_canonical_serialization() -> None:
    goal = await _establish()
    serialized = "00000000-0000-0000-0000-000000000001|Open a second location|1"

    assert goal.identity_serialization == serialized
    assert goal.goal_id == uuid.uuid5(BUSINESS_GOALS_NAMESPACE, serialized)
    assert uuid.UUID("6f4c2e91-8b73-4d56-a1c9-27e5b0f34d82") == (
        BUSINESS_GOALS_NAMESPACE
    )


@pytest.mark.asyncio
async def test_establishment_requires_authorized_owner_and_matching_declarant() -> None:
    draft = _draft()
    _, actor_id = _ids()
    service = BusinessGoalService()

    with pytest.raises(PermissionError, match="owner authorization"):
        await service.establish_draft(
            actor_id=actor_id,
            draft=draft,
            authorization=OwnerAuthorizationFake(False),
        )
    with pytest.raises(PermissionError, match="match the Goal declarant"):
        await service.establish_draft(
            actor_id=uuid.UUID(int=3),
            draft=draft,
            authorization=OwnerAuthorizationFake(True),
        )


@pytest.mark.asyncio
async def test_authorized_establishment_is_deterministic_and_preserves_structure(
) -> None:
    draft = _draft()
    first = await _establish(draft)
    second = await _establish(draft)

    assert first == second
    assert first.lifecycle is GoalLifecycle.DRAFT
    assert first.declaration.text == "Open a second location"
    assert first.provenance.source_type is GoalProvenanceSourceType.OWNER
    assert first.evidence[0].reference == "owner-evidence-1"
    assert first.unavailable_information[0].reason == "not supplied"


@pytest.mark.asyncio
async def test_published_goal_is_immutable_and_publication_transition_is_one_way(
) -> None:
    draft = await _establish()
    published = BusinessGoalService.publish(draft=draft, published_history=())

    assert published.lifecycle is GoalLifecycle.PUBLISHED
    with pytest.raises(FrozenInstanceError):
        published.goal_version = "2"
    with pytest.raises(ValueError, match="only a Draft"):
        BusinessGoalService.publish(draft=published, published_history=())


@pytest.mark.asyncio
async def test_correction_uses_a_new_version_and_preserves_published_history() -> None:
    service = BusinessGoalService()
    published = BusinessGoalService.publish(
        draft=await _establish(), published_history=()
    )
    correction = _draft(version="2")
    _, actor_id = _ids()

    corrected_draft = await service.establish_correction_draft(
        actor_id=actor_id,
        published_goal=published,
        correction=correction,
        authorization=OwnerAuthorizationFake(True),
    )
    corrected = service.publish(
        draft=corrected_draft,
        published_history=(published,),
    )

    assert published.goal_version == "1"
    assert corrected.goal_version == "2"
    assert published.goal_id != corrected.goal_id
    assert service.history(
        published_history=(corrected, published), business_id=published.business_id
    ) == (published, corrected)


@pytest.mark.asyncio
async def test_invalid_correction_and_published_identity_conflict_are_rejected(
) -> None:
    published = BusinessGoalService.publish(
        draft=await _establish(), published_history=()
    )
    _, actor_id = _ids()
    service = BusinessGoalService()

    with pytest.raises(ValueError, match="new goal version"):
        await service.establish_correction_draft(
            actor_id=actor_id,
            published_goal=published,
            correction=_draft(version="1"),
            authorization=OwnerAuthorizationFake(True),
        )
    with pytest.raises(ValueError, match="identity and version conflict"):
        service.publish(draft=await _establish(), published_history=(published,))


@pytest.mark.asyncio
async def test_current_and_history_are_business_isolated_and_non_ranking() -> None:
    first = BusinessGoalService.publish(draft=await _establish(), published_history=())
    later_draft = _draft(subject="Expand the catalogue", version="1")
    later = BusinessGoalService.publish(
        draft=await _establish(later_draft),
        published_history=(),
    )
    other_business = BusinessGoalService.publish(
        draft=await _establish(_draft(business_id=uuid.UUID(int=9))),
        published_history=(),
    )
    expired = BusinessGoalService.publish(
        draft=await _establish(
            _draft(version="3", effective_until=_time() + timedelta(days=1))
        ),
        published_history=(),
    )

    assert BusinessGoalService.current(
        published_history=(later, expired, other_business, first),
        business_id=first.business_id,
        context_time=_time() + timedelta(days=2),
    ) == (later, first)
    assert BusinessGoalService.history(
        published_history=(later, other_business, first),
        business_id=first.business_id,
    ) == (later, first)


def test_temporal_context_requires_explicit_timezone() -> None:
    naive = datetime(2026, 8, 30)

    with pytest.raises(ValueError, match="explicit timezone"):
        GoalTemporalContext(naive)


def test_goal_model_rejects_an_identity_not_derived_from_the_contract() -> None:
    draft = _draft()

    with pytest.raises(ValueError, match="canonical UUID5"):
        BusinessGoal(
            goal_id=uuid.UUID(int=99),
            business_id=draft.business_id,
            canonical_subject=draft.canonical_subject,
            goal_version=draft.goal_version,
            declaration=draft.declaration,
            provenance=draft.provenance,
            temporal_context=draft.temporal_context,
            lifecycle=GoalLifecycle.DRAFT,
        )


def test_provenance_and_lifecycle_reject_unapproved_vocabulary() -> None:
    with pytest.raises(ValueError, match="source type"):
        GoalProvenance(
            cast(GoalProvenanceSourceType, "system"), uuid.UUID(int=2), _time()
        )

    goal = _draft()
    with pytest.raises(ValueError, match="lifecycle"):
        BusinessGoal(
            goal_id=uuid.uuid5(BUSINESS_GOALS_NAMESPACE, goal.identity_serialization),
            business_id=goal.business_id,
            canonical_subject=goal.canonical_subject,
            goal_version=goal.goal_version,
            declaration=goal.declaration,
            provenance=goal.provenance,
            temporal_context=goal.temporal_context,
            lifecycle=cast(GoalLifecycle, "published"),
        )


def test_service_has_no_direct_business_membership_persistence_dependency() -> None:
    source = Path(business_goal_service.__file__).read_text(encoding="utf-8")

    assert "modules.business.repository.membership" not in source


def test_read_port_is_technology_neutral_and_has_no_persistence_dependency() -> None:
    assert isinstance(GoalReadProviderFake(), BusinessGoalReadProvider)
