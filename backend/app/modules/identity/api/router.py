"""Identity API router."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.identity.api.dependencies import get_registration_service
from app.modules.identity.dependencies import CurrentUser
from app.modules.identity.schemas import CreateUserRequest, UserResponse
from app.modules.identity.services import RegistrationService

router = APIRouter(prefix="/identity", tags=["Identity"])
RegistrationServiceDependency = Annotated[
    RegistrationService,
    Depends(get_registration_service),
]


@router.post(
    "/register",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register identity user",
    description=(
        "Creates a pending identity user, stores credentials, assigns the default "
        "member role, and publishes the user-created identity event."
    ),
    responses={
        HTTPStatus.CREATED: {
            "description": "User registered successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "User registered successfully",
                        "data": {
                            "id": "018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4",
                            "email": "owner@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "display_name": "Jane Doe",
                            "status": "pending",
                            "last_login_at": None,
                            "failed_login_attempts": 0,
                            "locked_until": None,
                        },
                    }
                }
            },
        },
        HTTPStatus.BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Request validation failed.",
        },
        HTTPStatus.CONFLICT: {
            "model": ErrorResponse,
            "description": "Email address already exists.",
        },
        HTTPStatus.INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error.",
        },
    },
)
async def register_user(
    request: CreateUserRequest,
    registration_service: RegistrationServiceDependency,
) -> SuccessResponse[UserResponse]:
    """Register a new identity user."""
    user = await registration_service.register_user(request)
    return SuccessResponse(
        success=True,
        message="User registered successfully",
        data=user,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current identity user",
    description="Returns the identity profile for the authenticated bearer token.",
    responses={
        HTTPStatus.OK: {
            "description": "Current user returned successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4",
                        "email": "owner@example.com",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "display_name": "Jane Doe",
                        "status": "active",
                        "last_login_at": None,
                        "failed_login_attempts": 0,
                        "locked_until": None,
                    }
                }
            },
        },
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication is missing or invalid.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authenticated user is not permitted.",
        },
        HTTPStatus.INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error.",
        },
    },
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the current authenticated identity user."""
    return UserResponse.model_validate(current_user)
