"""Tests for pagination and filtering framework primitives."""

import pytest
from pydantic import ValidationError

from app.common.filters import FilterCondition, FilterParams, SortCondition
from app.common.pagination import Page, PaginationMeta, PaginationParams

EXPECTED_OFFSET = 50
EXPECTED_LARGE_PAGE_SIZE = 25
EXPECTED_META_PAGES = 3
EXPECTED_CREATED_PAGE = 2
EXPECTED_CREATED_PAGES = 6


def test_pagination_params_calculate_offset_and_limit() -> None:
    """Pagination parameters expose SQL-friendly offset and limit values."""
    params = PaginationParams(page=3, size=25)

    assert params.offset == EXPECTED_OFFSET
    assert params.limit == EXPECTED_LARGE_PAGE_SIZE


def test_pagination_meta_calculates_pages() -> None:
    """Pagination metadata calculates page counts."""
    meta = PaginationMeta(page=1, size=20, total=41)

    assert meta.pages == EXPECTED_META_PAGES


def test_page_create_builds_paginated_container() -> None:
    """Page factory combines items and pagination metadata."""
    page = Page[int].create(
        items=[1, 2],
        total=12,
        params=PaginationParams(page=2, size=2),
    )

    assert page.items == [1, 2]
    assert page.meta.page == EXPECTED_CREATED_PAGE
    assert page.meta.pages == EXPECTED_CREATED_PAGES


def test_filter_params_store_filter_and_sort_conditions() -> None:
    """Filter parameters preserve filter and sort instructions."""
    filters = FilterParams(
        filters=[FilterCondition(field="status", operator="eq", value="active")],
        sort=[SortCondition(field="created_at", direction="desc")],
    )

    assert filters.filters[0].field == "status"
    assert filters.sort[0].direction == "desc"


def test_pagination_rejects_invalid_page() -> None:
    """Pagination parameters reject invalid pages."""
    with pytest.raises(ValidationError):
        PaginationParams(page=0)
