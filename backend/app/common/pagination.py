"""Reusable pagination primitives."""

from typing import Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItemT = TypeVar("ItemT")


class PaginationParams(BaseModel):
    """Input parameters for offset-based pagination."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        """Return the SQL offset for the current page."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Return the SQL limit for the current page."""
        return self.size


class PaginationMeta(BaseModel):
    """Metadata describing a paginated result set."""

    model_config = ConfigDict(extra="forbid")

    page: int
    size: int
    total: int
    pages: int = 0

    @model_validator(mode="after")
    def calculate_pages(self) -> Self:
        """Calculate page count after validation."""
        self.pages = 0 if self.total == 0 else ((self.total - 1) // self.size) + 1
        return self


class Page[ItemT](BaseModel):
    """Paginated data container."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    items: list[ItemT]
    meta: PaginationMeta

    @classmethod
    def create(
        cls,
        *,
        items: list[ItemT],
        total: int,
        params: PaginationParams,
    ) -> "Page[ItemT]":
        """Create a page from items, total count, and pagination parameters."""
        return cls(
            items=items,
            meta=PaginationMeta(page=params.page, size=params.size, total=total),
        )
