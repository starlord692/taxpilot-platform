"""Live PostgreSQL concurrency & claim fencing tests (EP-RC1.9 Remediation).

Verifies SKIP LOCKED non-blocking mutual exclusion across concurrent workers,
conditional claim fencing in PostgreSQL, and failure isolation for unhandled
events.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.outbox.models import OutboxEventRecord
from app.common.outbox.relay import OutboxRelay
from app.common.outbox.repository import OutboxRepository
from app.core.model_registry import import_all_models
from app.modules.business.models import Business
from app.modules.business.models.enums import BusinessStatus, BusinessType

import_all_models()

# Fail-closed module mark: Skip all tests in this file when RUN_LIVE_POSTGRES_TESTS is not enabled.
_opt_in = os.getenv("RUN_LIVE_POSTGRES_TESTS", "").strip().lower()
if _opt_in not in {"true", "1", "yes"}:
    pytestmark = [
        pytest.mark.asyncio,
        pytest.mark.skip(
            reason="Live PostgreSQL integration tests require RUN_LIVE_POSTGRES_TESTS=true and OUTBOX_TEST_DATABASE_URL"
        ),
    ]
else:
    pytestmark = pytest.mark.asyncio


DISPOSABLE_DB_PATTERN = re.compile(
    r"^taxpilot_test_disposable_(?P<session_id>[a-zA-Z0-9_-]+)_(?P<timestamp>[0-9]+)$"
)
FORBIDDEN_DATABASES = frozenset({
    "taxpilot",
    "postgres",
    "template0",
    "template1",
    "taxpilot_dev",
    "taxpilot_prod",
})
ALLOWED_TEST_DB_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
})


def _validate_disposable_postgres_url(raw_url: str | None, context: str) -> str:
    """Parse and validate live test database URL without opening network sockets.

    Fails closed:
    1. Rejects missing or whitespace-only URLs.
    2. Parses URL structure without exposing raw connection strings or credentials.
    3. Restricts hosts strictly to local loopback (localhost, 127.0.0.1, ::1).
    4. Rejects 'taxpilot', 'postgres', and all persistent databases.
    5. Enforces ephemeral naming: 'taxpilot_test_disposable_{session_id}_{timestamp}'.
    """
    if not raw_url or not raw_url.strip():
        pytest.fail(
            f"RUN_LIVE_POSTGRES_TESTS is enabled, but no database URL is configured for {context}."
        )

    clean_url = raw_url.strip()
    try:
        parsed = make_url(clean_url)
    except Exception:
        pytest.fail(
            f"Malformed database URL for {context}. Unable to parse URL structure."
        )

    if not parsed.get_backend_name().startswith("postgresql"):
        pytest.fail(
            f"Invalid backend '{parsed.get_backend_name()}' for {context}. "
            "Live PostgreSQL tests require a postgresql driver."
        )

    if not parsed.host or not parsed.host.strip():
        pytest.fail(
            f"Malformed database URL for {context}: host component is missing or empty."
        )

    normalized_host = parsed.host.strip().lower().strip("[]")
    if normalized_host not in ALLOWED_TEST_DB_HOSTS:
        pytest.fail(
            f"Disallowed database host in {context}. "
            "Live PostgreSQL integration tests are strictly restricted to local loopback hosts: "
            "localhost, 127.0.0.1, or ::1."
        )

    db_name = (parsed.database or "").strip()
    if not db_name:
        pytest.fail(
            f"Malformed database URL for {context}: database name component is missing or empty."
        )

    if db_name.lower() in FORBIDDEN_DATABASES:
        pytest.fail(
            f"Unsafe database name in {context}. Access to 'taxpilot', 'postgres', "
            "and persistent production/dev databases is strictly forbidden during tests."
        )

    if not DISPOSABLE_DB_PATTERN.match(db_name):
        pytest.fail(
            f"Database name in {context} violates safety policy. "
            "Live PostgreSQL tests strictly require a disposable test database matching "
            "'taxpilot_test_disposable_{session_id}_{timestamp}'."
        )

    return clean_url


def _get_live_postgres_url() -> str:
    """Resolve live PostgreSQL test database URL.

    Fails closed: Requires explicit RUN_LIVE_POSTGRES_TESTS=true opt-in AND
    an explicit OUTBOX_TEST_DATABASE_URL or POSTGRES_TEST_DATABASE_URL.
    Validates URL format and disposable database name without connecting to the server.
    Never attempts connectivity probing and never defaults to localhost:5432.
    """
    opt_in = os.getenv("RUN_LIVE_POSTGRES_TESTS", "").strip().lower()
    if opt_in not in {"true", "1", "yes"}:
        pytest.skip(
            "Live PostgreSQL integration tests disabled by default. "
            "To enable, set RUN_LIVE_POSTGRES_TESTS=true and OUTBOX_TEST_DATABASE_URL."
        )
    raw_url = (
        os.getenv("OUTBOX_TEST_DATABASE_URL")
        or os.getenv("POSTGRES_TEST_DATABASE_URL")
    )
    return _validate_disposable_postgres_url(raw_url, context="Outbox PostgreSQL tests")


@asynccontextmanager
async def pg_test_context() -> AsyncGenerator[
    tuple[async_sessionmaker[AsyncSession], uuid.UUID], None
]:
    """Provide a session factory and persistent business in an async context manager."""
    database_url = _get_live_postgres_url()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    b_id = uuid.uuid4()
    async with factory() as session:
        business = Business(
            id=b_id,
            legal_name=f"Test Business {uuid.uuid4().hex[:6]}",
            business_type=BusinessType.PRIVATE_LIMITED,
            status=BusinessStatus.ACTIVE,
        )
        session.add(business)
        await session.commit()

    try:
        yield factory, b_id
    finally:
        try:
            async with factory() as session:
                await session.execute(delete(Business).where(Business.id == b_id))
                await session.commit()
        finally:
            await engine.dispose()


TOTAL_BATCH_SIZE = 10


async def test_postgres_skip_locked_concurrency() -> None:
    """P1-C: Workers claiming batches via SKIP LOCKED never claim duplicate records.

    Ensures zero overlap between worker partitions.
    """
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        batch_test_tag = f"test.concurrency.{uuid.uuid4().hex[:8]}"
        inserted_ids: list[uuid.UUID] = []

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            for i in range(TOTAL_BATCH_SIZE):
                record = await repo.add(
                    business_id=test_business_id,
                    event_name=batch_test_tag,
                    event_payload={"index": i},
                )
                inserted_ids.append(record.id)
            await session.commit()

        try:
            barrier = asyncio.Barrier(2)

            # Launch two workers claiming concurrently with different worker identities
            async def claim_worker(worker_id: str, limit: int) -> list[uuid.UUID]:
                async with pg_session_factory() as session:
                    repo = OutboxRepository(session)
                    claimed = await repo.claim_pending(limit=limit, worker_id=worker_id)
                    # Hold transaction until both have executed SKIP LOCKED
                    await barrier.wait()
                    await session.commit()
                    return [rec.id for rec in claimed]

            worker_1_claims, worker_2_claims = await asyncio.gather(
                claim_worker("worker-conc-1", 5),
                claim_worker("worker-conc-2", 5),
            )

            # Invariant: Each worker must receive disjoint sets of records
            claimed_intersection = set(worker_1_claims) & set(worker_2_claims)
            assert len(claimed_intersection) == 0, (
                f"Concurrent workers claimed overlapping events: {claimed_intersection}"
            )

            total_claimed = set(worker_1_claims) | set(worker_2_claims)
            assert len(total_claimed) == TOTAL_BATCH_SIZE
            assert total_claimed == set(inserted_ids)
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(
                        OutboxEventRecord.id.in_(inserted_ids)
                    )
                )
                await session.commit()


async def test_postgres_conditional_claim_fencing() -> None:
    """P1-A & P1-C: Claim fencing prevents stale worker from updating claimed record.

    Ensures worker identity mismatch rejects status changes.
    """
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        event_tag = f"test.fencing.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=test_business_id,
                event_name=event_tag,
                event_payload={"test": "fencing"},
            )
            event_id = record.id
            await session.commit()

        try:
            # Worker A claims the event
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                claimed = await repo.claim_pending(limit=1, worker_id="worker-owner-A")
                await session.commit()
                assert any(rec.id == event_id for rec in claimed)

            # Stale Worker B attempts to complete it
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                update_published = await repo.mark_published(
                    event_id, worker_id="worker-stale-B"
                )
                update_failed = await repo.mark_failed(
                    event_id, "Stale error", worker_id="worker-stale-B"
                )
                await session.commit()

                # Both updates MUST be rejected
                assert update_published is False
                assert update_failed is False

            # Legitimate Worker A completes it
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                update_published = await repo.mark_published(
                    event_id, worker_id="worker-owner-A"
                )
                await session.commit()

                assert update_published is True

            # Verify final state in PostgreSQL
            async with pg_session_factory() as session:
                result = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert result is not None
                assert result.status == "PUBLISHED"
                assert result.published_at is not None
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


async def test_postgres_unhandled_event_failure_isolation() -> None:
    """P0-A & P1-C: Unhandled event transitions to FAILED/PENDING, never PUBLISHED.

    Ensures poison or unknown events do not falsely report successful delivery.
    """
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        unhandled_event_name = f"unregistered.event.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=test_business_id,
                event_name=unhandled_event_name,
                event_payload={"data": "poison"},
            )
            event_id = record.id
            await session.commit()

        try:
            # Create an OutboxRelay with NO subscriber for unhandled_event_name
            relay = OutboxRelay(session_factory=pg_session_factory, batch_size=1)

            # Run a single batch poll
            processed_count = await relay.process_batch()
            assert processed_count == 1

            # Verify that record was NOT marked PUBLISHED
            async with pg_session_factory() as session:
                result = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert result is not None
                assert result.status != "PUBLISHED"
                assert result.status == "PENDING"
                assert result.retry_count == 1
                assert "No subscriber registered" in (result.last_error or "")
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


MAX_TEST_RETRIES = 3


async def test_postgres_stale_claim_reassignment() -> None:
    """F-05-R / P1-C: Expired lease allows reassignment to new worker identity.

    Verifies:
    1. Worker A claims an event (status -> PROCESSING).
    2. Event lease expires (claimed_at backdated past stale_threshold_seconds).
    3. Worker B claims the event via claim_pending (stale claim reassigned).
    4. Stale Worker A is rejected on mark_published and mark_failed.
    5. Authorized Worker B completes mark_published successfully.
    """
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        event_tag = f"test.stale_claim.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=test_business_id,
                event_name=event_tag,
                event_payload={"step": "reclaim_test"},
            )
            event_id = record.id
            await session.commit()

        try:
            # 1. Worker A claims the event
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                claimed_a = await repo.claim_pending(
                    limit=1, worker_id="worker-A", stale_threshold_seconds=300
                )
                assert len(claimed_a) == 1 and claimed_a[0].claimed_by == "worker-A"
                await session.commit()

            # 2. Simulate lease expiration: backdate claimed_at by 600 seconds
            stale_time = datetime.now(UTC) - timedelta(seconds=600)
            async with pg_session_factory() as session:
                await session.execute(
                    update(OutboxEventRecord)
                    .where(OutboxEventRecord.id == event_id)
                    .values(claimed_at=stale_time)
                )
                await session.commit()

            # 3. Worker B reclaims the expired event
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                claimed_b = await repo.claim_pending(
                    limit=1, worker_id="worker-B", stale_threshold_seconds=300
                )
                assert len(claimed_b) == 1 and claimed_b[0].claimed_by == "worker-B"
                await session.commit()

            # 4. Stale Worker A is rejected; Authorized Worker B succeeds
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                stale_pub = await repo.mark_published(event_id, worker_id="worker-A")
                stale_fail = await repo.mark_failed(
                    event_id, "Stale worker crash", worker_id="worker-A"
                )
                auth_pub = await repo.mark_published(event_id, worker_id="worker-B")
                await session.commit()
                assert stale_pub is False and stale_fail is False and auth_pub is True

            # 5. Verify final DB state in PostgreSQL
            async with pg_session_factory() as session:
                result = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert result is not None and result.status == "PUBLISHED"
                assert result.published_at is not None
                assert result.claimed_by == "worker-B"
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


async def test_postgres_poison_pill_dead_letter_isolation() -> None:
    """F-03 / F-05: Exceeding max_retries transitions to DEAD_LETTER in PostgreSQL."""
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        poison_tag = f"test.poison.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=test_business_id,
                event_name=poison_tag,
                event_payload={"error": "poison_pill"},
            )
            event_id = record.id
            record.max_retries = MAX_TEST_RETRIES
            await session.commit()

        try:
            worker_id = "poison-tester"
            for cycle in range(1, MAX_TEST_RETRIES + 1):
                async with pg_session_factory() as session:
                    repo = OutboxRepository(session)
                    claimed = await repo.claim_pending(limit=1, worker_id=worker_id)
                    assert len(claimed) == 1 and claimed[0].id == event_id
                    failed = await repo.mark_failed(
                        event_id, f"Handler crash {cycle}", worker_id=worker_id
                    )
                    assert failed is True
                    await session.commit()

            # Cycle after max retries: event is DEAD_LETTER and cannot be claimed
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                assert len(await repo.claim_pending(limit=1, worker_id=worker_id)) == 0
                result = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert result is not None
                assert result.status == "DEAD_LETTER"
                assert result.retry_count == MAX_TEST_RETRIES
                assert result.claimed_by is None
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


async def test_postgres_worker_fencing_rejects_missing_identity() -> None:
    """Task 2.1: Repository API rejects missing worker identity before DB mutation."""
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, test_business_id):
        event_tag = f"test.empty_id.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=test_business_id,
                event_name=event_tag,
                event_payload={"test": "empty_id"},
            )
            event_id = record.id
            await session.commit()

        try:
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                with pytest.raises(ValueError, match="worker_id is required"):
                    await repo.mark_published(event_id, worker_id="")

                with pytest.raises(ValueError, match="worker_id is required"):
                    await repo.mark_published(event_id, worker_id="   ")

                with pytest.raises(ValueError, match="worker_id is required"):
                    await repo.mark_failed(event_id, "error", worker_id="")

                with pytest.raises(ValueError, match="worker_id is required"):
                    await repo.mark_failed(event_id, "error", worker_id="   ")

                # Verify database record remains untouched in PENDING status
                result = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert result is not None
                assert result.status == "PENDING"
                assert result.retry_count == 0
                assert result.claimed_by is None
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


async def test_postgres_business_delete_restricted_by_outbox_events() -> None:
    """FD-2: Direct delete of business rejected when outbox events exist."""
    database_url = _get_live_postgres_url()

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    b_id = uuid.uuid4()

    # Create isolated business
    async with factory() as session:
        business = Business(
            id=b_id,
            legal_name=f"Restrict Test Business {uuid.uuid4().hex[:6]}",
            business_type=BusinessType.PRIVATE_LIMITED,
            status=BusinessStatus.ACTIVE,
        )
        session.add(business)
        await session.commit()

    # Create outbox event referencing the business
    async with factory() as session:
        repo = OutboxRepository(session)
        await repo.add(
            business_id=b_id,
            event_name="test.business.created",
            event_payload={"test": "restrict_delete"},
        )
        await session.commit()

    try:
        # Attempt to delete the business directly in PostgreSQL — must fail
        async with factory() as session:
            with pytest.raises(IntegrityError) as exc_info:
                await session.execute(delete(Business).where(Business.id == b_id))
                await session.commit()
            err_msg = str(exc_info.value).lower()
            assert (
                "outbox_events_business_id_fkey" in err_msg
                or "violates foreign key constraint" in err_msg
            )

        # Verify the business and outbox event are both still intact in PostgreSQL
        async with factory() as session:
            persisted_biz = await session.scalar(
                select(Business).where(Business.id == b_id)
            )
            assert persisted_biz is not None
            persisted_event = await session.scalar(
                select(OutboxEventRecord).where(OutboxEventRecord.business_id == b_id)
            )
            assert persisted_event is not None
            assert persisted_event.status == "PENDING"
    finally:
        # Clean up outbox event first, then business
        async with factory() as session:
            await session.execute(
                delete(OutboxEventRecord).where(OutboxEventRecord.business_id == b_id)
            )
            await session.execute(delete(Business).where(Business.id == b_id))
            await session.commit()
        await engine.dispose()


async def test_postgres_outbox_event_nullable_business_id() -> None:
    """FD-2: Outbox event with nullable business_id persists and processes."""
    _get_live_postgres_url()

    async with pg_test_context() as (pg_session_factory, _):
        event_tag = f"system.reconciliation.{uuid.uuid4().hex[:8]}"

        async with pg_session_factory() as session:
            repo = OutboxRepository(session)
            record = await repo.add(
                business_id=None,
                event_name=event_tag,
                event_payload={"system": "reconciliation_pulse"},
            )
            event_id = record.id
            await session.commit()

        try:
            async with pg_session_factory() as session:
                repo = OutboxRepository(session)
                # Verify event was persisted with business_id is None
                persisted = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert persisted is not None
                assert persisted.business_id is None
                assert persisted.status == "PENDING"

                # Verify claiming works on nullable business_id
                claimed = await repo.claim_pending(
                    worker_id="worker-null-biz", limit=50
                )
                matching = [c for c in claimed if c.id == event_id]
                assert len(matching) == 1
                assert matching[0].business_id is None
                assert matching[0].status == "PROCESSING"

                # Verify marking published works
                marked = await repo.mark_published(
                    event_id, worker_id="worker-null-biz"
                )
                assert marked is True

                persisted_after = await session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                assert persisted_after is not None
                assert persisted_after.status == "PUBLISHED"
                assert persisted_after.business_id is None
        finally:
            async with pg_session_factory() as session:
                await session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await session.commit()


async def test_postgres_business_soft_archive_preserves_outbox_events() -> None:
    """FD-2: Existing soft-archive workflow succeeds and preserves outbox events."""
    database_url = _get_live_postgres_url()

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    b_id = uuid.uuid4()

    # Create active business
    async with factory() as session:
        business = Business(
            id=b_id,
            legal_name=f"Archive Test Business {uuid.uuid4().hex[:6]}",
            business_type=BusinessType.PRIVATE_LIMITED,
            status=BusinessStatus.ACTIVE,
        )
        session.add(business)
        await session.commit()

    # Create outbox event
    async with factory() as session:
        repo = OutboxRepository(session)
        record = await repo.add(
            business_id=b_id,
            event_name="test.business.invoice_staged",
            event_payload={"invoice_id": str(uuid.uuid4())},
        )
        event_id = record.id
        await session.commit()

    try:
        # Execute soft-archive workflow as performed by BusinessService.archive_business
        async with factory() as session:
            b = await session.scalar(select(Business).where(Business.id == b_id))
            assert b is not None
            b.status = BusinessStatus.ARCHIVED
            session.add(b)
            await session.commit()

        # Verify business is archived and outbox event remains intact
        async with factory() as session:
            b = await session.scalar(select(Business).where(Business.id == b_id))
            assert b is not None
            assert b.status == BusinessStatus.ARCHIVED

            ev = await session.scalar(
                select(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
            )
            assert ev is not None
            assert ev.status == "PENDING"
            assert ev.business_id == b_id
    finally:
        async with factory() as session:
            await session.execute(
                delete(OutboxEventRecord).where(OutboxEventRecord.business_id == b_id)
            )
            await session.execute(delete(Business).where(Business.id == b_id))
            await session.commit()
        await engine.dispose()



