"""GST provider configuration model."""

from sqlalchemy import Boolean, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.abstract import BaseEntity
from app.modules.gst.einvoice.models.enums import GSTProviderType


class GSTProvider(BaseEntity):
    """Provider configuration for GST integrations."""

    __tablename__ = "gst_providers"
    __table_args__ = (
        Index("ix_gst_providers_name", "name", unique=True),
        Index("ix_gst_providers_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    provider_type: Mapped[GSTProviderType] = mapped_column(
        Enum(GSTProviderType, name="gst_provider_type"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
