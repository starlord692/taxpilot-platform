"""Shared API response schemas."""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.common.pagination import PaginationMeta

DataT = TypeVar("DataT")


class ApiResponse[DataT](BaseModel):
    """Standard API response envelope."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    data: DataT | None = None


class ErrorDetail(BaseModel):
    """Structured API error detail."""

    model_config = ConfigDict(extra="forbid")

    code: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(ApiResponse[ErrorDetail]):
    """Standard API error response envelope."""


class PaginatedApiResponse[DataT](ApiResponse[list[DataT]]):
    """Standard API response envelope for paginated lists."""

    meta: PaginationMeta
