"""Document storage abstractions."""

import hashlib
import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Abstract storage backend for uploaded documents."""

    @abstractmethod
    async def save(
        self,
        *,
        business_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> str:
        """Persist content and return a storage path."""

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete content from storage."""

    @abstractmethod
    async def read(self, storage_path: str) -> bytes:
        """Read content from storage."""


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str) -> None:
        """Initialize local storage root."""
        self._base_path = Path(base_path)

    async def save(
        self,
        *,
        business_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> str:
        """Persist content to local storage."""
        digest = hashlib.sha256(content).hexdigest()
        safe_name = Path(filename).name
        business_path = self._base_path / str(business_id)
        business_path.mkdir(parents=True, exist_ok=True)
        destination = business_path / f"{digest}-{safe_name}"
        destination.write_bytes(content)
        return str(destination)

    async def delete(self, storage_path: str) -> None:
        """Delete a stored file if it exists."""
        path = Path(storage_path)
        if path.exists() and path.is_file():
            path.unlink()

    async def read(self, storage_path: str) -> bytes:
        """Read content from local storage."""
        return Path(storage_path).read_bytes()
