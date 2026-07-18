"""Document automation repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models.abstract.timestamp import utc_now
from app.common.repositories import BaseRepository
from app.modules.documents.automation.models import (
    AutomationRun,
    AutomationState,
    AutomationType,
)


class AutomationRunRepository(BaseRepository[AutomationRun]):
    """Repository for automation run metadata."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, AutomationRun)

    async def create_started(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        automation_type: AutomationType,
        idempotency_key: str,
    ) -> AutomationRun:
        """Create a running automation run."""
        return await self.add(
            AutomationRun(
                document_id=document_id,
                business_id=business_id,
                automation_type=automation_type,
                idempotency_key=idempotency_key,
                status=AutomationState.RUNNING,
                started_at=utc_now(),
                retry_count=0,
            )
        )

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return latest automation run for a document."""
        result = await self.session.execute(
            select(AutomationRun)
            .where(
                AutomationRun.document_id == document_id,
                AutomationRun.is_deleted.is_(False),
            )
            .order_by(AutomationRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AutomationRun | None:
        """Return automation run by idempotency key."""
        result = await self.session.execute(
            select(AutomationRun).where(
                AutomationRun.idempotency_key == idempotency_key,
                AutomationRun.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_running_for_document(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return running automation for a document."""
        result = await self.session.execute(
            select(AutomationRun).where(
                AutomationRun.document_id == document_id,
                AutomationRun.status == AutomationState.RUNNING,
                AutomationRun.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        run: AutomationRun,
        *,
        erp_record_type: str,
        erp_record_id: uuid.UUID,
    ) -> AutomationRun:
        """Mark automation completed."""
        run.status = AutomationState.COMPLETED
        run.erp_record_type = erp_record_type
        run.erp_record_id = erp_record_id
        run.completed_at = utc_now()
        self.session.add(run)
        await self.session.flush()
        return run

    async def mark_failed(
        self,
        run: AutomationRun,
        *,
        reason: str,
    ) -> AutomationRun:
        """Mark automation failed."""
        run.status = AutomationState.FAILED
        run.failure_reason = reason
        run.completed_at = utc_now()
        run.retry_count += 1
        self.session.add(run)
        await self.session.flush()
        return run

    async def mark_rolled_back(
        self,
        run: AutomationRun,
        *,
        reason: str,
    ) -> AutomationRun:
        """Mark automation rolled back."""
        run.status = AutomationState.ROLLED_BACK
        run.failure_reason = reason
        run.completed_at = utc_now()
        run.retry_count += 1
        self.session.add(run)
        await self.session.flush()
        return run
