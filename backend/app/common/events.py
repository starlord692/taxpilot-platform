"""In-process event dispatching framework."""

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

EventT = TypeVar("EventT", bound="Event")


class Event:
    """Base class for framework events."""

    event_name = "event"


EventHandler = Callable[[EventT], Awaitable[None] | None]


class EventDispatcher:
    """Dispatch events to registered in-process handlers."""

    def __init__(self) -> None:
        """Initialize an empty handler registry."""
        self._handlers: dict[type[Event], list[EventHandler[Any]]] = defaultdict(list)

    def register(
        self,
        event_type: type[EventT],
        handler: EventHandler[EventT],
    ) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)

    async def dispatch(self, event: EventT) -> None:
        """Dispatch an event to all handlers registered for its concrete type."""
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            result = handler(event)
            if inspect.isawaitable(result):
                await result

    def clear(self) -> None:
        """Remove all registered event handlers."""
        self._handlers.clear()
