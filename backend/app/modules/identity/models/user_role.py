"""Identity user-role association model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.common.models.abstract.timestamp import utc_now

if TYPE_CHECKING:
    from app.modules.identity.models.role import IdentityRole
    from app.modules.identity.models.user import IdentityUser


class IdentityUserRole(BaseEntity):
    """Many-to-many association between users and roles."""

    __tablename__ = "identity_user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_identity_user_roles_user_role"),
        Index("ix_identity_user_roles_user_id", "user_id"),
        Index("ix_identity_user_roles_role_id", "role_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
    )

    user: Mapped[IdentityUser] = relationship(back_populates="roles")
    role: Mapped[IdentityRole] = relationship(back_populates="users")
