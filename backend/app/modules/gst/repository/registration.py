"""GST registration repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.gst.models import GSTRegistration
from app.modules.gst.schemas import GSTRegistrationCreate, GSTRegistrationUpdate


class GSTRegistrationRepository(BaseRepository[GSTRegistration]):
    """Repository for GST registration persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, GSTRegistration)

    async def create(
        self,
        request: GSTRegistrationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTRegistration:
        """Create a GST registration."""
        registration = GSTRegistration(
            **request.model_dump(),
            business_id=business_id,
        )
        return await self.add(registration)

    async def update(
        self,
        registration: GSTRegistration,
        request: GSTRegistrationUpdate,
    ) -> GSTRegistration:
        """Update GST registration fields."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(registration, field_name, value)
        self.session.add(registration)
        await self.session.flush()
        return registration

    async def deactivate(self, registration: GSTRegistration) -> GSTRegistration:
        """Deactivate a GST registration."""
        registration.is_active = False
        self.session.add(registration)
        await self.session.flush()
        return registration

    async def get_by_id(
        self,
        registration_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return registration by UUID."""
        result = await self.session.execute(
            self._base_statement().where(GSTRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_business(
        self,
        business_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return active GST registration for a business."""
        result = await self.session.execute(
            self._base_statement().where(
                GSTRegistration.business_id == business_id,
                GSTRegistration.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_gstin(self, gstin: str) -> GSTRegistration | None:
        """Return registration by GSTIN."""
        result = await self.session.execute(
            self._base_statement().where(GSTRegistration.gstin == gstin.upper())
        )
        return result.scalar_one_or_none()

    async def list(  # type: ignore[override]
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[GSTRegistration]:
        """List GST registrations for a business."""
        statement = (
            self._base_statement()
            .where(GSTRegistration.business_id == business_id)
            .order_by(GSTRegistration.created_at.desc())
        )
        return await self._paginate(statement, pagination)

    async def _paginate(
        self,
        statement: Select[tuple[GSTRegistration]],
        pagination: PaginationParams | None,
    ) -> Page[GSTRegistration]:
        """Paginate registration rows."""
        params = pagination or PaginationParams()
        total_result = await self.session.execute(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=int(total_result.scalar_one()),
            params=params,
        )

    def _base_statement(self) -> Select[tuple[GSTRegistration]]:
        """Return default select."""
        return select(GSTRegistration).where(GSTRegistration.is_deleted.is_(False))
