"""Identity role-permission association model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.identity.models.permission import IdentityPermission
    from app.modules.identity.models.role import IdentityRole


class IdentityRolePermission(BaseEntity):
    """Many-to-many association between roles and permissions."""

    __tablename__ = "identity_role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_identity_role_permissions_role_permission",
        ),
        Index("ix_identity_role_permissions_role_id", "role_id"),
        Index("ix_identity_role_permissions_permission_id", "permission_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("identity_permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[IdentityRole] = relationship(back_populates="permissions")
    permission: Mapped[IdentityPermission] = relationship(back_populates="roles")
