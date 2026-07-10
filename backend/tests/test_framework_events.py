"""Tests for the framework event dispatcher."""

from dataclasses import dataclass

import pytest

from app.common.events import Event, EventDispatcher

pytestmark = pytest.mark.asyncio

@dataclass(frozen=True)
class FrameworkEvent(Event):
    """Test event used by dispatcher tests."""

    value: int = 1


async def test_dispatcher_invokes_sync_and_async_handlers() -> None:
    """Dispatcher calls registered sync and async handlers."""
    dispatcher = EventDispatcher()
    handled: list[int] = []

    def sync_handler(event: FrameworkEvent) -> None:
        handled.append(event.value)

    async def async_handler(event: FrameworkEvent) -> None:
        handled.append(event.value + 1)

    dispatcher.register(FrameworkEvent, sync_handler)
    dispatcher.register(FrameworkEvent, async_handler)

    await dispatcher.dispatch(FrameworkEvent(value=10))

    assert handled == [10, 11]


async def test_dispatcher_clear_removes_handlers() -> None:
    """Clearing the dispatcher removes registered handlers."""
    dispatcher = EventDispatcher()
    handled: list[int] = []

    def handler(event: FrameworkEvent) -> None:
        handled.append(event.value)

    dispatcher.register(FrameworkEvent, handler)
    dispatcher.clear()

    await dispatcher.dispatch(FrameworkEvent())

    assert handled == []
