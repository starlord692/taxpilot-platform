"""Business repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessMembership,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
)
from app.modules.business.schemas import CreateBusinessRequest, UpdateBusinessRequest


class BusinessRepository(BaseRepository[Business]):
    """Repository for business persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Business)

    async def create_business(
        self,
        request: CreateBusinessRequest,
        *,
        business_code: str | None = None,
    ) -> Business:
        """Create a business aggregate from a request schema."""
        business = Business(
            business_code=business_code,
            legal_name=request.legal_name,
            trade_name=request.trade_name,
            business_type=request.business_type,
            registration_status=request.registration_status,
            business_email=request.business_email,
            business_phone=request.business_phone,
            website=request.website,
            status=BusinessStatus.ACTIVE,
        )
        if request.address is not None:
            business.address = BusinessAddress(**request.address.model_dump())
        if request.tax_profile is not None:
            business.tax_profile = BusinessTaxProfile(
                **request.tax_profile.model_dump()
            )
        if request.settings is not None:
            business.settings = BusinessSettings(**request.settings.model_dump())

        return await self.add(business)

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return a non-deleted business by UUID."""
        statement = self._base_business_statement().where(Business.id == business_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_business_code(self, business_code: str) -> Business | None:
        """Return a non-deleted business by business code."""
        statement = self._base_business_statement().where(
            Business.business_code == business_code,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        search: str | None = None,
        sort: str | None = None,
    ) -> Page[Business]:
        """Return paginated businesses for a user membership."""
        params = pagination or PaginationParams()
        statement = (
            self._base_business_statement()
            .join(BusinessMembership, BusinessMembership.business_id == Business.id)
            .where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.is_deleted.is_(False),
            )
        )
        total_statement = (
            select(Business)
            .join(BusinessMembership, BusinessMembership.business_id == Business.id)
            .where(
                Business.is_deleted.is_(False),
                BusinessMembership.user_id == user_id,
                BusinessMembership.is_deleted.is_(False),
            )
        )
        if search:
            search_expression = Business.legal_name.ilike(f"%{search}%")
            statement = statement.where(search_expression)
            total_statement = total_statement.where(search_expression)

        statement = self._apply_business_sort(statement, sort)
        total = await self.count_statement(total_statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().unique().all()),
            total=total,
            params=params,
        )

    async def update_business(
        self,
        business: Business,
        request: UpdateBusinessRequest,
    ) -> Business:
        """Update mutable business fields from a request schema."""
        update_data = request.model_dump(
            exclude_unset=True,
            exclude={"address", "tax_profile", "settings"},
        )
        for field_name, value in update_data.items():
            setattr(business, field_name, value)
        self.session.add(business)
        await self.session.flush()
        return business

    async def archive_business(self, business: Business) -> Business:
        """Mark a business as archived."""
        business.status = BusinessStatus.ARCHIVED
        self.session.add(business)
        await self.session.flush()
        return business

    async def restore_business(self, business: Business) -> Business:
        """Restore an archived or inactive business to active status."""
        business.status = BusinessStatus.ACTIVE
        self.session.add(business)
        await self.session.flush()
        return business

    async def exists_by_name(self, legal_name: str) -> bool:
        """Return whether a non-deleted business exists by legal name."""
        statement = select(Business.id).where(
            Business.legal_name == legal_name,
            Business.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, business_email: str) -> bool:
        """Return whether a non-deleted business exists by email."""
        statement = select(Business.id).where(
            Business.business_email == business_email.lower(),
            Business.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def exists_by_gstin(self, gstin: str) -> bool:
        """Return whether a non-deleted tax profile exists by GSTIN."""
        statement = (
            select(BusinessTaxProfile.id)
            .join(Business, Business.id == BusinessTaxProfile.business_id)
            .where(
                BusinessTaxProfile.gstin == gstin.upper(),
                BusinessTaxProfile.is_deleted.is_(False),
                Business.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def get_tax_profile(
        self,
        business_id: uuid.UUID,
    ) -> BusinessTaxProfile | None:
        """Return a non-deleted tax profile for a business."""
        statement = select(BusinessTaxProfile).where(
            BusinessTaxProfile.business_id == business_id,
            BusinessTaxProfile.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_settings(self, business_id: uuid.UUID) -> BusinessSettings | None:
        """Return non-deleted settings for a business."""
        statement = select(BusinessSettings).where(
            BusinessSettings.business_id == business_id,
            BusinessSettings.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def count_statement(self, statement: Select[tuple[Business]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())

    def _base_business_statement(self) -> Select[tuple[Business]]:
        """Return the standard business select with relationship loading."""
        return (
            select(Business)
            .options(
                selectinload(Business.address),
                selectinload(Business.tax_profile),
                selectinload(Business.settings),
                selectinload(Business.memberships),
            )
            .where(Business.is_deleted.is_(False))
        )

    def _apply_business_sort(
        self,
        statement: Select[tuple[Business]],
        sort: str | None,
    ) -> Select[tuple[Business]]:
        """Apply supported business list sorting."""
        sort_key = sort or "-created_at"
        direction = "desc" if sort_key.startswith("-") else "asc"
        field_name = sort_key.removeprefix("-")
        sort_columns = {
            "created_at": Business.created_at,
            "legal_name": Business.legal_name,
            "status": Business.status,
        }
        column = sort_columns.get(field_name, Business.created_at)
        return statement.order_by(
            column.desc() if direction == "desc" else column.asc()
        )
