"""Optimistic locking version mixin."""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class VersionMixin:
    """Provide an integer version for future optimistic locking."""

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
