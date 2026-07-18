"""Business aggregate root model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models.abstract import BaseEntity
from app.modules.business.models.enums import (
    BusinessStatus,
    BusinessType,
    RegistrationStatus,
)

if TYPE_CHECKING:
    from app.modules.business.models.address import BusinessAddress
    from app.modules.business.models.membership import BusinessMembership
    from app.modules.business.models.settings import BusinessSettings
    from app.modules.business.models.tax_profile import BusinessTaxProfile


class Business(BaseEntity):
    """Business entity owned or collaborated on by identity users."""

    __tablename__ = "businesses"
    __table_args__ = (
        Index("ix_businesses_legal_name", "legal_name"),
        Index("ix_businesses_status", "status"),
        Index("ix_businesses_business_type", "business_type"),
    )

    business_code: Mapped[str | None] = mapped_column(
        String(40),
        unique=True,
        nullable=True,
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, name="business_type"),
        nullable=False,
    )
    registration_status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus, name="business_registration_status"),
        default=RegistrationStatus.PENDING,
        nullable=False,
    )
    business_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BusinessStatus] = mapped_column(
        Enum(BusinessStatus, name="business_status"),
        default=BusinessStatus.ACTIVE,
        nullable=False,
    )

    address: Mapped[BusinessAddress | None] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tax_profile: Mapped[BusinessTaxProfile | None] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
        uselist=False,
    )
    settings: Mapped[BusinessSettings | None] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
        uselist=False,
    )
    memberships: Mapped[list[BusinessMembership]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
    )
