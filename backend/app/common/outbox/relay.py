"""In-process PostgreSQL Transactional Outbox Relay."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import socket
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.common.outbox.repository import OutboxRepository
from app.core.logging import get_logger

logger = get_logger(__name__)

RelayEventHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class OutboxRelay:
    """Background outbox processor delivering committed events (at-least-once)."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str | None = None,
        batch_size: int = 50,
        poll_interval_seconds: float = 1.0,
        stale_threshold_seconds: int = 300,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id or (
            f"relay-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._stale_threshold = stale_threshold_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._subscribers: dict[str, list[RelayEventHandler]] = {}

    @property
    def worker_id(self) -> str:
        """Return the unique worker identifier for this relay instance."""
        return self._worker_id

    def subscribe(self, event_name: str, handler: RelayEventHandler) -> None:
        """Register a handler for a committed outbox event."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)

    def start(self) -> None:
        """Start the background relay processing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("outbox_relay_started", extra={"worker_id": self._worker_id})

    async def stop(self) -> None:
        """Gracefully stop the background relay processing loop."""
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("outbox_relay_stopped", extra={"worker_id": self._worker_id})

    async def _run_loop(self) -> None:
        """Continuously poll and dispatch outbox events until stopped."""
        while self._running:
            try:
                processed = await self.process_batch()
                if processed == 0:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "outbox_relay_loop_error",
                    extra={"error": str(exc)},
                    exc_info=True,
                )
                await asyncio.sleep(self._poll_interval)

    async def process_batch(self) -> int:
        """Claim and dispatch a single batch of pending outbox events."""
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            claims = await repo.claim_pending(
                limit=self._batch_size,
                worker_id=self._worker_id,
                stale_threshold_seconds=self._stale_threshold,
            )
            if not claims:
                return 0

            # Commit the claim transition to avoid locking row across handlers
            await session.commit()

        # Dispatch each event in its own transaction for strict failure isolation
        processed_count = 0
        for event in claims:
            await self._dispatch_single_event(
                event.id,
                event.event_name,
                event.event_payload,
            )
            processed_count += 1

        return processed_count

    async def _dispatch_single_event(
        self,
        event_id: Any,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        """Dispatch a single event to registered handlers with failure isolation."""
        handlers = self._subscribers.get(event_name, [])
        error_msg: str | None = None

        if not handlers:
            error_msg = f"No subscriber registered for outbox event '{event_name}'"
            logger.warning(
                "outbox_event_unhandled",
                extra={
                    "event_id": str(event_id),
                    "event_name": event_name,
                    "worker_id": self._worker_id,
                },
            )
        else:
            try:
                for handler in handlers:
                    res = handler(event_name, payload)
                    if inspect.isawaitable(res):
                        await res
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "outbox_event_dispatch_failed",
                    extra={
                        "event_id": str(event_id),
                        "event_name": event_name,
                        "error": error_msg,
                        "worker_id": self._worker_id,
                    },
                    exc_info=True,
                )

        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            if error_msg is not None:
                updated = await repo.mark_failed(
                    event_id,
                    error_msg,
                    worker_id=self._worker_id,
                )
            else:
                updated = await repo.mark_published(
                    event_id,
                    worker_id=self._worker_id,
                )
            await session.commit()
            if not updated:
                logger.warning(
                    "outbox_claim_fencing_rejected",
                    extra={
                        "event_id": str(event_id),
                        "worker_id": self._worker_id,
                        "target_status": "FAILED" if error_msg else "PUBLISHED",
                    },
                )
