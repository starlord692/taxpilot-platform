"""Identity permission model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.identity.models.role_permission import IdentityRolePermission


class IdentityPermission(BaseEntity):
    """Permission that can be attached to roles."""

    __tablename__ = "identity_permissions"
    __table_args__ = (Index("ix_identity_permissions_name", "name"),)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    roles: Mapped[list[IdentityRolePermission]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )
