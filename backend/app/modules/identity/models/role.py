"""Identity role model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.identity.models.role_permission import IdentityRolePermission
    from app.modules.identity.models.user_role import IdentityUserRole


class IdentityRole(BaseEntity):
    """Role that can be assigned to identity users."""

    __tablename__ = "identity_roles"
    __table_args__ = (Index("ix_identity_roles_name", "name"),)

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list[IdentityUserRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[list[IdentityRolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
