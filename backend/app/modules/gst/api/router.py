"""GST Foundation API router."""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.pagination import PaginationParams
from app.core.responses import ErrorResponse, PaginatedApiResponse, SuccessResponse
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.gst.api.dependencies import (
    get_gst_code_service,
    get_gst_registration_service,
    get_gst_settings_service,
    get_gst_tax_rate_service,
    get_gst_unit_of_work,
)
from app.modules.gst.schemas import (
    GSTRegistrationCreate,
    GSTRegistrationResponse,
    GSTRegistrationUpdate,
    GSTSettingsCreate,
    GSTSettingsResponse,
    GSTSettingsUpdate,
    GSTTaxRateCreate,
    GSTTaxRateResponse,
    GSTTaxRateUpdate,
    HSNCodeCreate,
    HSNCodeResponse,
    HSNCodeUpdate,
    SACCodeCreate,
    SACCodeResponse,
    SACCodeUpdate,
)
from app.modules.gst.services import (
    GSTCodeService,
    GSTRegistrationService,
    GSTSettingsService,
    GSTTaxRateService,
)
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/gst", tags=["GST Foundation"])
RegistrationServiceDep = Annotated[
    GSTRegistrationService,
    Depends(get_gst_registration_service),
]
TaxRateServiceDep = Annotated[GSTTaxRateService, Depends(get_gst_tax_rate_service)]
SettingsServiceDep = Annotated[GSTSettingsService, Depends(get_gst_settings_service)]
CodeServiceDep = Annotated[GSTCodeService, Depends(get_gst_code_service)]
GSTUnitOfWorkDep = Annotated[Any, Depends(get_gst_unit_of_work)]


@router.post(
    "/registrations",
    response_model=SuccessResponse[GSTRegistrationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create GST registration",
    description="Creates GST registration information for a business.",
    responses={
        HTTPStatus.CREATED: {"description": "GST registration created."},
        HTTPStatus.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatus.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_registration(
    request: GSTRegistrationCreate,
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: RegistrationServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[GSTRegistrationResponse]:
    """Create GST registration."""
    await _ensure_business_member(uow, business_id, current_user.id)
    registration = await service.create_registration(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="GST registration created successfully",
        data=registration,
    )


@router.get(
    "/registrations",
    response_model=PaginatedApiResponse[GSTRegistrationResponse],
    summary="List GST registrations",
    description="Lists GST registrations for a business.",
)
async def list_registrations(
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: RegistrationServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedApiResponse[GSTRegistrationResponse]:
    """List GST registrations."""
    await _ensure_business_member(uow, business_id, current_user.id)
    result = await service.list_registrations(
        business_id=business_id,
        pagination=PaginationParams(page=page, size=page_size),
    )
    return PaginatedApiResponse(
        success=True,
        message="GST registrations returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.patch(
    "/registrations/{registration_id}",
    response_model=SuccessResponse[GSTRegistrationResponse],
    summary="Update GST registration",
    description="Updates GST registration information.",
)
async def update_registration(
    registration_id: uuid.UUID,
    request: GSTRegistrationUpdate,
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: RegistrationServiceDep,
) -> SuccessResponse[GSTRegistrationResponse]:
    """Update GST registration."""
    await _ensure_registration_member(uow, registration_id, current_user.id)
    registration = await service.update_registration(registration_id, request)
    return SuccessResponse(
        success=True,
        message="GST registration updated successfully",
        data=registration,
    )


@router.delete(
    "/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate GST registration",
    description="Deactivates GST registration information.",
)
async def deactivate_registration(
    registration_id: uuid.UUID,
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: RegistrationServiceDep,
) -> Response:
    """Deactivate GST registration."""
    await _ensure_registration_member(uow, registration_id, current_user.id)
    await service.deactivate_registration(registration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tax-rates",
    response_model=SuccessResponse[GSTTaxRateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create GST tax rate",
    description="Creates a reusable GST tax rate.",
)
async def create_tax_rate(
    request: GSTTaxRateCreate,
    current_user: CurrentUser,
    service: TaxRateServiceDep,
) -> SuccessResponse[GSTTaxRateResponse]:
    """Create GST tax rate."""
    _ = current_user
    tax_rate = await service.create_tax_rate(request)
    return SuccessResponse(
        success=True,
        message="GST tax rate created successfully",
        data=tax_rate,
    )


@router.get(
    "/tax-rates",
    response_model=PaginatedApiResponse[GSTTaxRateResponse],
    summary="List GST tax rates",
    description="Lists reusable GST tax rates.",
)
async def list_tax_rates(
    current_user: CurrentUser,
    service: TaxRateServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    active_only: Annotated[bool, Query()] = False,
) -> PaginatedApiResponse[GSTTaxRateResponse]:
    """List GST tax rates."""
    _ = current_user
    result = await service.list_tax_rates(
        PaginationParams(page=page, size=page_size),
        active_only=active_only,
    )
    return PaginatedApiResponse(
        success=True,
        message="GST tax rates returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.patch(
    "/tax-rates/{tax_rate_id}",
    response_model=SuccessResponse[GSTTaxRateResponse],
    summary="Update GST tax rate",
    description="Updates a reusable GST tax rate.",
)
async def update_tax_rate(
    tax_rate_id: uuid.UUID,
    request: GSTTaxRateUpdate,
    current_user: CurrentUser,
    service: TaxRateServiceDep,
) -> SuccessResponse[GSTTaxRateResponse]:
    """Update GST tax rate."""
    _ = current_user
    tax_rate = await service.update_tax_rate(tax_rate_id, request)
    return SuccessResponse(
        success=True,
        message="GST tax rate updated successfully",
        data=tax_rate,
    )


@router.delete(
    "/tax-rates/{tax_rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate GST tax rate",
    description="Deactivates a reusable GST tax rate.",
)
async def deactivate_tax_rate(
    tax_rate_id: uuid.UUID,
    current_user: CurrentUser,
    service: TaxRateServiceDep,
) -> Response:
    """Deactivate GST tax rate."""
    _ = current_user
    await service.deactivate_tax_rate(tax_rate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/hsn-codes",
    response_model=SuccessResponse[HSNCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create HSN code",
    description="Creates an HSN code mapping.",
)
async def create_hsn_code(
    request: HSNCodeCreate,
    current_user: CurrentUser,
    service: CodeServiceDep,
) -> SuccessResponse[HSNCodeResponse]:
    """Create HSN code."""
    _ = current_user
    code = await service.create_hsn_code(request)
    return SuccessResponse(success=True, message="HSN code created", data=code)


@router.get(
    "/hsn-codes",
    response_model=PaginatedApiResponse[HSNCodeResponse],
    summary="List HSN codes",
    description="Lists HSN code mappings.",
)
async def list_hsn_codes(
    current_user: CurrentUser,
    service: CodeServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedApiResponse[HSNCodeResponse]:
    """List HSN codes."""
    _ = current_user
    result = await service.list_hsn_codes(PaginationParams(page=page, size=page_size))
    return PaginatedApiResponse(
        success=True,
        message="HSN codes returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.patch(
    "/hsn-codes/{code_id}",
    response_model=SuccessResponse[HSNCodeResponse],
    summary="Update HSN code",
    description="Updates an HSN code mapping.",
)
async def update_hsn_code(
    code_id: uuid.UUID,
    request: HSNCodeUpdate,
    current_user: CurrentUser,
    service: CodeServiceDep,
) -> SuccessResponse[HSNCodeResponse]:
    """Update HSN code."""
    _ = current_user
    code = await service.update_hsn_code(code_id, request)
    return SuccessResponse(success=True, message="HSN code updated", data=code)


@router.post(
    "/sac-codes",
    response_model=SuccessResponse[SACCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create SAC code",
    description="Creates a SAC code mapping.",
)
async def create_sac_code(
    request: SACCodeCreate,
    current_user: CurrentUser,
    service: CodeServiceDep,
) -> SuccessResponse[SACCodeResponse]:
    """Create SAC code."""
    _ = current_user
    code = await service.create_sac_code(request)
    return SuccessResponse(success=True, message="SAC code created", data=code)


@router.get(
    "/sac-codes",
    response_model=PaginatedApiResponse[SACCodeResponse],
    summary="List SAC codes",
    description="Lists SAC code mappings.",
)
async def list_sac_codes(
    current_user: CurrentUser,
    service: CodeServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedApiResponse[SACCodeResponse]:
    """List SAC codes."""
    _ = current_user
    result = await service.list_sac_codes(PaginationParams(page=page, size=page_size))
    return PaginatedApiResponse(
        success=True,
        message="SAC codes returned successfully",
        data=result.items,
        meta=result.meta,
    )


@router.patch(
    "/sac-codes/{code_id}",
    response_model=SuccessResponse[SACCodeResponse],
    summary="Update SAC code",
    description="Updates a SAC code mapping.",
)
async def update_sac_code(
    code_id: uuid.UUID,
    request: SACCodeUpdate,
    current_user: CurrentUser,
    service: CodeServiceDep,
) -> SuccessResponse[SACCodeResponse]:
    """Update SAC code."""
    _ = current_user
    code = await service.update_sac_code(code_id, request)
    return SuccessResponse(success=True, message="SAC code updated", data=code)


@router.post(
    "/settings",
    response_model=SuccessResponse[GSTSettingsResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create GST settings",
    description="Creates GST settings for a business.",
)
async def create_settings(
    request: GSTSettingsCreate,
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: SettingsServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[GSTSettingsResponse]:
    """Create GST settings."""
    await _ensure_business_member(uow, business_id, current_user.id)
    settings = await service.create_settings(request, business_id=business_id)
    return SuccessResponse(
        success=True,
        message="GST settings created successfully",
        data=settings,
    )


@router.get(
    "/settings",
    response_model=SuccessResponse[GSTSettingsResponse],
    summary="Get GST settings",
    description="Returns GST settings for a business.",
)
async def get_settings(
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: SettingsServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[GSTSettingsResponse]:
    """Return GST settings."""
    await _ensure_business_member(uow, business_id, current_user.id)
    settings = await service.get_settings(business_id)
    return SuccessResponse(
        success=True,
        message="GST settings returned successfully",
        data=settings,
    )


@router.patch(
    "/settings",
    response_model=SuccessResponse[GSTSettingsResponse],
    summary="Update GST settings",
    description="Updates GST settings for a business.",
)
async def update_settings(
    request: GSTSettingsUpdate,
    current_user: CurrentUser,
    uow: GSTUnitOfWorkDep,
    service: SettingsServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
) -> SuccessResponse[GSTSettingsResponse]:
    """Update GST settings."""
    await _ensure_business_member(uow, business_id, current_user.id)
    settings = await service.update_settings(business_id, request)
    return SuccessResponse(
        success=True,
        message="GST settings updated successfully",
        data=settings,
    )


async def _ensure_registration_member(
    uow: Any,
    registration_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Ensure the user belongs to the registration's business."""
    async with uow:
        registration = await uow.gst_registrations.get_by_id(registration_id)
        if registration is None:
            return
        await _ensure_business_member(
            uow,
            registration.business_id,
            user_id,
            entered=True,
        )


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    entered: bool = False,
) -> None:
    """Raise when current user is not a business member."""
    if not entered:
        async with uow:
            await _ensure_business_member(uow, business_id, user_id, entered=True)
        return
    if not await uow.business_memberships.is_member(
        business_id=business_id,
        user_id=user_id,
    ):
        raise BusinessNotMemberException(
            "User is not a member of the business",
            details={"business_id": str(business_id), "user_id": str(user_id)},
        )
