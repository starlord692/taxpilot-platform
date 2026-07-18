"""Account category model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity

if TYPE_CHECKING:
    from app.modules.accounting.chart_of_accounts.models.account_type import (
        AccountType,
    )


class AccountCategory(BaseEntity):
    """Top-level account category for chart of accounts classification."""

    __tablename__ = "account_categories"
    __table_args__ = (Index("ix_account_categories_name", "name"),)

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    account_types: Mapped[list[AccountType]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )
