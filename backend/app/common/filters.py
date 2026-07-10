"""Reusable filtering and sorting primitives."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FilterOperator = Literal["eq", "ne", "lt", "lte", "gt", "gte", "like", "ilike", "in"]
SortDirection = Literal["asc", "desc"]


class FilterCondition(BaseModel):
    """A single field filter condition."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    operator: FilterOperator = "eq"
    value: str | int | float | bool | list[str | int | float | bool]


class SortCondition(BaseModel):
    """A single field sort condition."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    direction: SortDirection = "asc"


class FilterParams(BaseModel):
    """Collection of filtering and sorting instructions."""

    model_config = ConfigDict(extra="forbid")

    filters: list[FilterCondition] = Field(default_factory=list)
    sort: list[SortCondition] = Field(default_factory=list)
