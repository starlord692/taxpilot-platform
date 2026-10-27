"""Repository managing Outbox event persistence and claiming."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.outbox.models import OutboxEventRecord


class OutboxRepository:
    """PostgreSQL transactional outbox repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        event_name: str,
        payload: dict[str, Any] | None = None,
        event_payload: dict[str, Any] | None = None,
        business_id: uuid.UUID | None = None,
        event_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> OutboxEventRecord:
        """Stage an outbox event within the active transaction."""
        now = datetime.now(UTC)
        final_payload = event_payload if event_payload is not None else (payload or {})
        record = OutboxEventRecord(
            id=event_id or uuid.uuid4(),
            business_id=business_id,
            event_name=event_name,
            event_payload=final_payload,
            occurred_at=occurred_at or now,
            status="PENDING",
            retry_count=0,
            max_retries=5,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def claim_pending(
        self,
        *,
        limit: int = 50,
        worker_id: str = "relay",
        stale_threshold_seconds: int = 300,
    ) -> Sequence[OutboxEventRecord]:
        """Claim pending or stale processing events using SKIP LOCKED."""
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(seconds=stale_threshold_seconds)

        stmt = select(OutboxEventRecord).where(
            or_(
                OutboxEventRecord.status == "PENDING",
                (OutboxEventRecord.status == "PROCESSING")
                & (OutboxEventRecord.claimed_at < stale_cutoff),
            )
        ).order_by(OutboxEventRecord.occurred_at.asc()).limit(limit)

        bind = self._session.bind
        dialect_name = bind.dialect.name if bind is not None else ""
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        result = await self._session.execute(stmt)
        records = result.scalars().all()

        for record in records:
            record.status = "PROCESSING"
            record.claimed_at = now
            record.claimed_by = worker_id

        if records:
            await self._session.flush()

        return records

    async def mark_published(
        self,
        event_id: uuid.UUID,
        *,
        worker_id: str,
    ) -> bool:
        """Mark an event as successfully published using atomic claim fencing.

        Requires non-empty worker_id matching the active lease.
        """
        if not worker_id or not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError(
                "worker_id is required and cannot be empty for mark_published"
            )

        now = datetime.now(UTC)
        conditions = [
            OutboxEventRecord.id == event_id,
            OutboxEventRecord.status == "PROCESSING",
            OutboxEventRecord.claimed_by == worker_id,
        ]

        stmt = (
            update(OutboxEventRecord)
            .where(*conditions)
            .values(
                status="PUBLISHED",
                published_at=now,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        raw_rowcount = getattr(result, "rowcount", None)
        rowcount = raw_rowcount if isinstance(raw_rowcount, int) else 0
        return rowcount > 0

    async def mark_failed(
        self,
        event_id: uuid.UUID,
        error: str,
        *,
        worker_id: str,
    ) -> bool:
        """Record delivery failure atomically.

        Requires non-empty worker_id matching the active lease.
        Increments retries and isolates poison pills.
        """
        if not worker_id or not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError(
                "worker_id is required and cannot be empty for mark_failed"
            )

        now = datetime.now(UTC)
        conditions = [
            OutboxEventRecord.id == event_id,
            OutboxEventRecord.status == "PROCESSING",
            OutboxEventRecord.claimed_by == worker_id,
        ]

        new_retry_count = OutboxEventRecord.retry_count + 1
        new_status = case(
            (new_retry_count >= OutboxEventRecord.max_retries, "DEAD_LETTER"),
            else_="PENDING",
        )

        stmt = (
            update(OutboxEventRecord)
            .where(*conditions)
            .values(
                retry_count=new_retry_count,
                status=new_status,
                last_error=error,
                claimed_at=None,
                claimed_by=None,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        raw_rowcount = getattr(result, "rowcount", None)
        rowcount = raw_rowcount if isinstance(raw_rowcount, int) else 0
        return rowcount > 0

    async def get_by_id(self, event_id: uuid.UUID) -> OutboxEventRecord | None:
        """Retrieve an outbox event record by UUID."""
        return await self._session.get(OutboxEventRecord, event_id)

    async def count_by_status(self) -> dict[str, int]:
        """Return counts of outbox events grouped by status."""
        stmt = (
            select(OutboxEventRecord.status, func.count(OutboxEventRecord.id))
            .group_by(OutboxEventRecord.status)
        )
        result = await self._session.execute(stmt)
        return {str(status): int(count) for status, count in result.all()}
