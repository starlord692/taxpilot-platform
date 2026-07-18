"""Account type model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.accounting.chart_of_accounts.models.account import Account
    from app.modules.accounting.chart_of_accounts.models.category import (
        AccountCategory,
    )


class AccountType(BaseEntity):
    """Account type within a category, such as Asset or Expense."""

    __tablename__ = "account_types"
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "name",
            name="uq_account_types_category_name",
        ),
        Index("ix_account_types_category_id", "category_id"),
        Index("ix_account_types_name", "name"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("account_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    category: Mapped[AccountCategory] = relationship(back_populates="account_types")
    accounts: Mapped[list[Account]] = relationship(
        back_populates="account_type",
    )
