"""Business membership model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.business.models.business import Business
    from app.modules.identity.models.user import IdentityUser


class BusinessMembership(BaseEntity):
    """Association between an identity user and a business."""

    __tablename__ = "business_memberships"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "user_id",
            name="uq_business_memberships_business_user",
        ),
        Index("ix_business_memberships_business_id", "business_id"),
        Index("ix_business_memberships_user_id", "user_id"),
        Index("ix_business_memberships_role", "role"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(80), nullable=False)

    business: Mapped[Business] = relationship(back_populates="memberships")
    user: Mapped[IdentityUser] = relationship()
