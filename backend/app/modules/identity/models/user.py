"""Identity user model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.common.models.abstract import BaseEntity
from app.modules.identity.models.enums import UserStatus

if TYPE_CHECKING:
    from app.modules.identity.models.credential import IdentityCredential
    from app.modules.identity.models.email_verification import IdentityEmailVerification
    from app.modules.identity.models.login_history import IdentityLoginHistory
    from app.modules.identity.models.password_reset import IdentityPasswordReset
    from app.modules.identity.models.refresh_token import IdentityRefreshToken
    from app.modules.identity.models.user_role import IdentityUserRole


class IdentityUser(BaseEntity):
    """Identity user database model."""

    __tablename__ = "identity_users"
    __table_args__ = (
        Index("ix_identity_users_email", "email"),
        Index("ix_identity_users_status", "status"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="identity_user_status"),
        default=UserStatus.PENDING,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)

    credential: Mapped[IdentityCredential | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    roles: Mapped[list[IdentityUserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[IdentityRefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_verifications: Mapped[list[IdentityEmailVerification]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_resets: Mapped[list[IdentityPasswordReset]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    login_history: Mapped[list[IdentityLoginHistory]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @validates("email")
    def normalize_email(self, key: str, email: str) -> str:
        """Normalize email addresses before persistence."""
        return email.lower()
