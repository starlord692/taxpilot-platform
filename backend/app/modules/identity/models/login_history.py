"""Identity login history model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now

if TYPE_CHECKING:
    from app.modules.identity.models.user import IdentityUser


class IdentityLoginHistory(BaseEntity):
    """Login attempt history for an identity user."""

    __tablename__ = "identity_login_history"
    __table_args__ = (
        Index("ix_identity_login_history_user_id", "user_id"),
        Index("ix_identity_login_history_login_at", "login_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[IdentityUser] = relationship(back_populates="login_history")
