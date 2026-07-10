"""Shared API response schemas."""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class ApiResponse[DataT](BaseModel):
    """Standard API response envelope."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    data: DataT | None = None
