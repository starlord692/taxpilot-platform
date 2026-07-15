"""Unit of Work interface."""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


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
