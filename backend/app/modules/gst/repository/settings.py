"""GST settings repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.gst.models import GSTSettings
from app.modules.gst.schemas import GSTSettingsCreate, GSTSettingsUpdate


class GSTSettingsRepository(BaseRepository[GSTSettings]):
    """Repository for GST settings persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, GSTSettings)

    async def create(
        self,
        request: GSTSettingsCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTSettings:
        """Create GST settings for a business."""
        settings = GSTSettings(**request.model_dump(), business_id=business_id)
        return await self.add(settings)

    async def update(
        self,
        settings: GSTSettings,
        request: GSTSettingsUpdate,
    ) -> GSTSettings:
        """Update GST settings."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(settings, field_name, value)
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def get_by_business(self, business_id: uuid.UUID) -> GSTSettings | None:
        """Return GST settings for a business."""
        result = await self.session.execute(
            select(GSTSettings).where(
                GSTSettings.business_id == business_id,
                GSTSettings.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, settings_id: uuid.UUID) -> GSTSettings | None:
        """Return GST settings by UUID."""
        result = await self.session.execute(
            select(GSTSettings).where(
                GSTSettings.id == settings_id,
                GSTSettings.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()
