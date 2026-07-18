"""Business account model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.accounting.chart_of_accounts.models.account_type import (
        AccountType,
    )
    from app.modules.business.models import Business


class Account(BaseEntity):
    """Account owned by one business chart of accounts."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "account_code",
            name="uq_accounts_business_account_code",
        ),
        Index("ix_accounts_business_id", "business_id"),
        Index("ix_accounts_account_type_id", "account_type_id"),
        Index("ix_accounts_parent_account_id", "parent_account_id"),
        Index("ix_accounts_account_name", "account_name"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("account_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship()
    account_type: Mapped[AccountType] = relationship(back_populates="accounts")
    parent_account: Mapped[Account | None] = relationship(
        back_populates="child_accounts",
        remote_side="Account.id",
    )
    child_accounts: Mapped[list[Account]] = relationship(
        back_populates="parent_account",
        cascade="all, delete-orphan",
    )
