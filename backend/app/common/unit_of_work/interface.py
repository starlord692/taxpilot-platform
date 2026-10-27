"""Unit of Work interface."""

import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Self

PostCommitHook = Callable[[], Awaitable[None] | None]


def supports_uow(func: Any) -> bool:
    """Return True if callable accepts a 'uow' parameter."""
    if not callable(func):
        return False
    try:
        sig = inspect.signature(func)
        return "uow" in sig.parameters
    except (ValueError, TypeError):
        return False


class UnitOfWork(ABC):
    """Abstract asynchronous Unit of Work contract."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Enter a transactional Unit of Work scope."""

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit a transactional Unit of Work scope."""

    @abstractmethod
    async def commit(self) -> None:
        """Commit the active transaction."""

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the active transaction."""

    @abstractmethod
    def on_commit(self, hook: PostCommitHook) -> None:
        """Register a callback executed only after transaction commit succeeds."""

    @property
    def is_active(self) -> bool:
        """Return whether the Unit of Work is currently active."""
        return False

