"""Identity refresh token model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.identity.models.user import IdentityUser


class IdentityRefreshToken(BaseEntity):
    """Persisted refresh token hash for an identity user."""

    __tablename__ = "identity_refresh_tokens"
    __table_args__ = (
        Index("ix_identity_refresh_tokens_user_id", "user_id"),
        Index("ix_identity_refresh_tokens_token_hash", "token_hash"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[IdentityUser] = relationship(back_populates="refresh_tokens")
