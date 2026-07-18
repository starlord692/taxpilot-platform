"""Tests for reusable SQLAlchemy base entity mixins."""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from sqlalchemy.schema import ColumnDefault

from app.common.models.abstract import BaseEntity


class ExampleEntity(BaseEntity):
    """Concrete test entity for validating abstract model behavior."""

    __tablename__ = "example_entities"


def get_column_default(column_name: str) -> ColumnDefault:
    """Return a mapped column default for the example entity."""
    default = ExampleEntity.__table__.c[column_name].default
    assert default is not None
    return cast(ColumnDefault, default)


def test_uuid_generation() -> None:
    """UUID primary key default generates UUID values."""
    uuid_factory = cast(Callable[[Any], uuid.UUID], get_column_default("id").arg)

    generated_id = uuid_factory(None)

    assert isinstance(generated_id, uuid.UUID)


def test_timestamp_defaults_are_timezone_aware() -> None:
    """Timestamp defaults produce timezone-aware datetimes."""
    created_factory = cast(
        Callable[[Any], datetime],
        get_column_default("created_at").arg,
    )
    updated_factory = cast(
        Callable[[Any], datetime],
        get_column_default("updated_at").arg,
    )

    created_at = created_factory(None)
    updated_at = updated_factory(None)

    assert created_at.tzinfo is not None
    assert updated_at.tzinfo is not None
    assert created_at.utcoffset() is not None
    assert updated_at.utcoffset() is not None


def test_soft_delete_marks_entity_without_physical_delete() -> None:
    """Soft delete behavior marks an entity and records deletion time."""
    entity = ExampleEntity()
    entity.is_deleted = False
    entity.deleted_at = None

    entity.mark_deleted()

    assert entity.is_deleted is True
    assert entity.deleted_at is not None
    assert entity.deleted_at.tzinfo is not None


def test_version_default() -> None:
    """Version default starts at one for optimistic locking."""
    version_default = cast(Any, get_column_default("version").arg)

    assert version_default == 1
