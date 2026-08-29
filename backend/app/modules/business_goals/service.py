"""Deterministic establishment, publication, and retrieval for Business Goals."""

import uuid
from dataclasses import replace
from datetime import datetime

from app.common.authorization.contracts import (
    OwnerAuthorizationContract,
    ProtectedOwnerOperation,
)
from app.modules.business_goals.models import (
    BUSINESS_GOALS_NAMESPACE,
    BusinessGoal,
    GoalDraftInput,
    GoalLifecycle,
)


class BusinessGoalService:
    """Apply only the frozen Business Goals v1.0 lifecycle semantics."""

    async def establish_draft(
        self,
        *,
        actor_id: uuid.UUID,
        draft: GoalDraftInput,
        authorization: OwnerAuthorizationContract,
    ) -> BusinessGoal:
        """Establish an owner-authorized, non-authoritative immutable draft."""
        decision = await authorization.authorize_owner_operation(
            actor_id=actor_id,
            business_id=draft.business_id,
            operation=ProtectedOwnerOperation.BUSINESS_GOAL_ESTABLISH_OR_CONFIRM,
        )
        if not decision.is_authorized:
            raise PermissionError("owner authorization is required for Business Goals")
        if draft.provenance.declared_by != actor_id:
            raise PermissionError("authorized actor must match the Goal declarant")
        return BusinessGoal(
            goal_id=uuid.uuid5(BUSINESS_GOALS_NAMESPACE, draft.identity_serialization),
            business_id=draft.business_id,
            canonical_subject=draft.canonical_subject,
            goal_version=draft.goal_version,
            declaration=draft.declaration,
            provenance=draft.provenance,
            temporal_context=draft.temporal_context,
            lifecycle=GoalLifecycle.DRAFT,
            evidence=draft.evidence,
            limitations=draft.limitations,
            unavailable_information=draft.unavailable_information,
        )

    async def establish_correction_draft(
        self,
        *,
        actor_id: uuid.UUID,
        published_goal: BusinessGoal,
        correction: GoalDraftInput,
        authorization: OwnerAuthorizationContract,
    ) -> BusinessGoal:
        """Establish a correction as a new-version draft without mutating history."""
        if published_goal.lifecycle is not GoalLifecycle.PUBLISHED:
            raise ValueError("only a Published Goal can be corrected")
        if (
            correction.business_id != published_goal.business_id
            or correction.canonical_subject != published_goal.canonical_subject
        ):
            raise ValueError("correction must preserve business and canonical subject")
        if correction.goal_version == published_goal.goal_version:
            raise ValueError("correction must use a new goal version")
        return await self.establish_draft(
            actor_id=actor_id,
            draft=correction,
            authorization=authorization,
        )

    @staticmethod
    def publish(
        *,
        draft: BusinessGoal,
        published_history: tuple[BusinessGoal, ...],
    ) -> BusinessGoal:
        """Publish a Draft without replacing an existing published version."""
        if draft.lifecycle is not GoalLifecycle.DRAFT:
            raise ValueError("only a Draft Goal can be published")
        if any(
            item.lifecycle is GoalLifecycle.PUBLISHED and item.goal_id == draft.goal_id
            for item in published_history
        ):
            raise ValueError("published Goal identity and version conflict")
        return replace(draft, lifecycle=GoalLifecycle.PUBLISHED)

    @staticmethod
    def current(
        *,
        published_history: tuple[BusinessGoal, ...],
        business_id: uuid.UUID,
        context_time: datetime,
    ) -> tuple[BusinessGoal, ...]:
        """Return applicable Published Goals in deterministic non-ranking order."""
        current = tuple(
            item
            for item in published_history
            if item.business_id == business_id
            and item.lifecycle is GoalLifecycle.PUBLISHED
            and item.temporal_context.effective_from <= context_time
            and (
                item.temporal_context.effective_until is None
                or context_time < item.temporal_context.effective_until
            )
        )
        ordered = tuple(sorted(current, key=lambda item: item.identity_serialization))
        identities = tuple(item.identity_serialization for item in ordered)
        if len(identities) != len(set(identities)):
            raise ValueError("multiple Published Goals share a canonical identity")
        return ordered

    @staticmethod
    def history(
        *,
        published_history: tuple[BusinessGoal, ...],
        business_id: uuid.UUID,
    ) -> tuple[BusinessGoal, ...]:
        """Return immutable Published Goals in deterministic non-ranking order."""
        history = tuple(
            item
            for item in published_history
            if item.business_id == business_id
            and item.lifecycle is GoalLifecycle.PUBLISHED
        )
        return tuple(sorted(history, key=lambda item: item.identity_serialization))
