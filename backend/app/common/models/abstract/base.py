"""Base entity combining all reusable abstract model mixins."""

from app.common.models.abstract.audit import AuditMixin
from app.common.models.abstract.soft_delete import SoftDeleteMixin
from app.common.models.abstract.timestamp import TimestampMixin
from app.common.models.abstract.uuid import UUIDMixin
from app.common.models.abstract.version import VersionMixin
from app.core.database import Base


class BaseEntity(
    UUIDMixin,
    TimestampMixin,
    AuditMixin,
    SoftDeleteMixin,
    VersionMixin,
    Base,
):
    """Abstract base entity for future TaxPilot AI database models."""

    __abstract__ = True
