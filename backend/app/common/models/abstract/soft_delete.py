"""Soft delete mixin for entities that should not be physically deleted."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract.timestamp import utc_now


class SoftDeleteMixin:
    """Provide soft delete fields and behavior."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def mark_deleted(self) -> None:
        """Mark the entity as deleted without removing its database row."""
        self.is_deleted = True
        self.deleted_at = utc_now()
