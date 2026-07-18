"""Business lifecycle service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.accounting.chart_of_accounts.services import ChartInitializerService
from app.modules.accounting.chart_of_accounts.services.chart_initializer import (
    ChartInitializerUnitOfWork,
)
from app.modules.business.events import (
    BusinessArchivedEvent,
    BusinessCreatedEvent,
    BusinessRestoredEvent,
    BusinessUpdatedEvent,
)
from app.modules.business.exceptions import (
    BusinessArchivedException,
    BusinessDuplicateNameException,
    BusinessNotFoundException,
    BusinessNotMemberException,
)
from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessMembership,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
)
from app.modules.business.schemas import (
    BusinessResponse,
    BusinessSettingsRequest,
    BusinessSummaryResponse,
    CreateBusinessRequest,
    UpdateBusinessRequest,
)

OWNER_ROLE = "owner"


class BusinessLifecycleRepository(Protocol):
    """Business repository behavior required by lifecycle operations."""

    async def create_business(
        self,
        request: CreateBusinessRequest,
        *,
        business_code: str | None = None,
    ) -> Business:
        """Create a business aggregate."""
        ...

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Return a business by UUID."""
        ...

    async def get_by_business_code(self, business_code: str) -> Business | None:
        """Return a business by business code."""
        ...

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        search: str | None = None,
        sort: str | None = None,
    ) -> Page[Business]:
        """Return businesses by user membership."""
        ...

    async def update_business(
        self,
        business: Business,
        request: UpdateBusinessRequest,
    ) -> Business:
        """Update business scalar fields."""
        ...

    async def archive_business(self, business: Business) -> Business:
        """Archive a business."""
        ...

    async def restore_business(self, business: Business) -> Business:
        """Restore a business."""
        ...

    async def exists_by_name(self, legal_name: str) -> bool:
        """Return whether a business exists by legal name."""
        ...


class BusinessMembershipLifecycleRepository(Protocol):
    """Membership repository behavior required by lifecycle operations."""

    async def add_member(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> BusinessMembership:
        """Add a business member."""
        ...

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether the user is a business member."""
        ...


class BusinessUnitOfWork(ChartInitializerUnitOfWork, Protocol):
    """Unit of Work contract required by business lifecycle operations."""

    businesses: BusinessLifecycleRepository
    business_memberships: BusinessMembershipLifecycleRepository

    async def __aenter__(self) -> "BusinessUnitOfWork":
        """Enter the business transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the business transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit business changes."""
        ...


UnitOfWorkFactory = Callable[[], BusinessUnitOfWork]


class BusinessChartInitializer(Protocol):
    """Chart initializer behavior required by business creation."""

    async def initialize_default_chart(
        self,
        business_id: uuid.UUID,
        uow: ChartInitializerUnitOfWork,
    ) -> object:
        """Initialize default chart records for a business."""
        ...


class BusinessService:
    """Coordinate business lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        chart_initializer: BusinessChartInitializer | None = None,
    ) -> None:
        """Initialize the service with injected dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._chart_initializer = chart_initializer or ChartInitializerService()

    async def create_business(
        self,
        request: CreateBusinessRequest,
        owner_user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Create a business and assign the creator as owner."""
        validated_request = self._ensure_settings(
            CreateBusinessRequest.model_validate(request)
        )

        async with self._unit_of_work_factory() as uow:
            if await uow.businesses.exists_by_name(validated_request.legal_name):
                raise BusinessDuplicateNameException(
                    "Business name already exists",
                    details={"legal_name": validated_request.legal_name},
                )

            business = await uow.businesses.create_business(validated_request)
            await uow.business_memberships.add_member(
                business_id=business.id,
                user_id=owner_user_id,
                role=OWNER_ROLE,
            )
            await self._chart_initializer.initialize_default_chart(
                business.id,
                uow,
            )
            await self._event_dispatcher.dispatch(
                BusinessCreatedEvent(
                    business_id=business.id,
                    owner_user_id=owner_user_id,
                )
            )
            await uow.commit()

        return BusinessResponse.model_validate(business)

    async def list_businesses(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        sort: str | None = None,
    ) -> Page[BusinessSummaryResponse]:
        """List businesses that belong to a user."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.businesses.list_by_user(
                user_id,
                pagination,
                search=search,
                sort=sort,
            )

        return Page.create(
            items=[
                BusinessSummaryResponse.model_validate(business)
                for business in page.items
            ],
            total=page.meta.total,
            params=pagination,
        )

    async def get_business(
        self,
        business_code: str,
        user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Return a business by code when the user is a member."""
        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business_by_code(uow, business_code)
            await self._ensure_member(uow, business.id, user_id)

        return BusinessResponse.model_validate(business)

    async def update_business(
        self,
        business_id: uuid.UUID,
        request: UpdateBusinessRequest,
    ) -> BusinessResponse:
        """Update a business profile and nested records."""
        validated_request = UpdateBusinessRequest.model_validate(request)

        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business(uow, business_id)
            self._ensure_not_archived(business)

            self._apply_nested_updates(business, validated_request)
            business = await uow.businesses.update_business(
                business,
                validated_request,
            )
            await self._event_dispatcher.dispatch(
                BusinessUpdatedEvent(business_id=business.id)
            )
            await uow.commit()

        return BusinessResponse.model_validate(business)

    async def update_business_by_code(
        self,
        business_code: str,
        request: UpdateBusinessRequest,
        user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Update a business by code when the user is a member."""
        validated_request = UpdateBusinessRequest.model_validate(request)

        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business_by_code(uow, business_code)
            await self._ensure_member(uow, business.id, user_id)
            self._ensure_not_archived(business)

            self._apply_nested_updates(business, validated_request)
            business = await uow.businesses.update_business(
                business,
                validated_request,
            )
            await self._event_dispatcher.dispatch(
                BusinessUpdatedEvent(business_id=business.id)
            )
            await uow.commit()

        return BusinessResponse.model_validate(business)

    async def archive_business(self, business_id: uuid.UUID) -> BusinessResponse:
        """Archive a business."""
        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business(uow, business_id)
            business = await uow.businesses.archive_business(business)
            await self._event_dispatcher.dispatch(
                BusinessArchivedEvent(business_id=business.id)
            )
            await uow.commit()

        return BusinessResponse.model_validate(business)

    async def archive_business_by_code(
        self,
        business_code: str,
        user_id: uuid.UUID,
    ) -> None:
        """Archive a business by code when the user is a member."""
        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business_by_code(uow, business_code)
            await self._ensure_member(uow, business.id, user_id)
            business = await uow.businesses.archive_business(business)
            await self._event_dispatcher.dispatch(
                BusinessArchivedEvent(business_id=business.id)
            )
            await uow.commit()

    async def restore_business(self, business_id: uuid.UUID) -> BusinessResponse:
        """Restore an archived business."""
        async with self._unit_of_work_factory() as uow:
            business = await self._get_existing_business(uow, business_id)
            business = await uow.businesses.restore_business(business)
            await self._event_dispatcher.dispatch(
                BusinessRestoredEvent(business_id=business.id)
            )
            await uow.commit()

        return BusinessResponse.model_validate(business)

    def _ensure_settings(
        self,
        request: CreateBusinessRequest,
    ) -> CreateBusinessRequest:
        """Ensure new businesses always receive settings."""
        if request.settings is not None:
            return request
        return request.model_copy(update={"settings": BusinessSettingsRequest()})

    async def _get_existing_business(
        self,
        uow: BusinessUnitOfWork,
        business_id: uuid.UUID,
    ) -> Business:
        """Return a business or raise a domain not-found error."""
        business = await uow.businesses.get_by_id(business_id)
        if business is None:
            raise BusinessNotFoundException(
                "Business not found",
                details={"business_id": str(business_id)},
            )
        return business

    async def _get_existing_business_by_code(
        self,
        uow: BusinessUnitOfWork,
        business_code: str,
    ) -> Business:
        """Return a business by code or raise a domain not-found error."""
        business = await uow.businesses.get_by_business_code(business_code)
        if business is None:
            raise BusinessNotFoundException(
                "Business not found",
                details={"business_code": business_code},
            )
        return business

    async def _ensure_member(
        self,
        uow: BusinessUnitOfWork,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Raise when the user is not a business member."""
        if not await uow.business_memberships.is_member(
            business_id=business_id,
            user_id=user_id,
        ):
            raise BusinessNotMemberException(
                "User is not a member of the business",
                details={
                    "business_id": str(business_id),
                    "user_id": str(user_id),
                },
            )

    def _ensure_not_archived(self, business: Business) -> None:
        """Raise when an archived business cannot be modified."""
        if business.status == BusinessStatus.ARCHIVED:
            raise BusinessArchivedException(
                "Business is archived",
                details={"business_id": str(business.id)},
            )

    def _apply_nested_updates(
        self,
        business: Business,
        request: UpdateBusinessRequest,
    ) -> None:
        """Apply nested request data to related business records."""
        if request.address is not None:
            if business.address is None:
                business.address = BusinessAddress(
                    business_id=business.id,
                    **request.address.model_dump(),
                )
            else:
                self._apply_values(business.address, request.address.model_dump())

        if request.settings is not None:
            if business.settings is None:
                business.settings = BusinessSettings(
                    business_id=business.id,
                    **request.settings.model_dump(),
                )
            else:
                self._apply_values(business.settings, request.settings.model_dump())

        if request.tax_profile is not None:
            if business.tax_profile is None:
                business.tax_profile = BusinessTaxProfile(
                    business_id=business.id,
                    **request.tax_profile.model_dump(),
                )
            else:
                self._apply_values(
                    business.tax_profile,
                    request.tax_profile.model_dump(),
                )

    def _apply_values(self, target: object, values: dict[str, object]) -> None:
        """Apply dictionary values to a model object."""
        for field_name, value in values.items():
            setattr(target, field_name, value)
