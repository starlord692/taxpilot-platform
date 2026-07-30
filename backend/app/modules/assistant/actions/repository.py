"""Assistant action repositories."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.assistant.actions.enums import AssistantActionStatus
from app.modules.assistant.actions.models import (
    AssistantActionDraft,
    AssistantActionResult,
)


class AssistantActionRepository(BaseRepository[AssistantActionDraft]):
    """Persistence operations for assistant-owned action drafts."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async SQLAlchemy session."""
        super().__init__(session, AssistantActionDraft)

    async def create_draft(self, draft: AssistantActionDraft) -> AssistantActionDraft:
        """Persist a new assistant action draft."""
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def get_by_id(
        self,
        *,
        draft_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> AssistantActionDraft | None:
        """Return one business-scoped action draft."""
        statement = select(AssistantActionDraft).where(
            AssistantActionDraft.id == draft_id,
            AssistantActionDraft.business_id == business_id,
            AssistantActionDraft.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_completed_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantActionDraft | None:
        """Return a completed draft for replay protection."""
        statement = select(AssistantActionDraft).where(
            AssistantActionDraft.business_id == business_id,
            AssistantActionDraft.idempotency_key == idempotency_key,
            AssistantActionDraft.status == AssistantActionStatus.COMPLETED,
            AssistantActionDraft.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_active_by_idempotency(
        self,
        *,
        business_id: uuid.UUID,
        idempotency_key: str,
    ) -> AssistantActionDraft | None:
        """Return any existing non-deleted draft for an idempotency key."""
        statement = select(AssistantActionDraft).where(
            AssistantActionDraft.business_id == business_id,
            AssistantActionDraft.idempotency_key == idempotency_key,
            AssistantActionDraft.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update_draft(self, draft: AssistantActionDraft) -> AssistantActionDraft:
        """Flush changes for an action draft."""
        self.session.add(draft)
        await self.session.flush()
        return draft


class AssistantActionResultRepository(BaseRepository[AssistantActionResult]):
    """Persistence operations for assistant action results."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async SQLAlchemy session."""
        super().__init__(session, AssistantActionResult)

    async def create_result(
        self, result: AssistantActionResult
    ) -> AssistantActionResult:
        """Persist an action result."""
        self.session.add(result)
        await self.session.flush()
        return result

    async def list_by_draft(self, draft_id: uuid.UUID) -> list[AssistantActionResult]:
        """Return results for one draft."""
        statement = select(AssistantActionResult).where(
            AssistantActionResult.draft_id == draft_id,
            AssistantActionResult.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
