"""Identity login API router."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.identity.api.dependencies import get_authentication_service
from app.modules.identity.schemas import LoginRequest
from app.modules.identity.services import AuthenticationResult, AuthenticationService

router = APIRouter(prefix="/identity", tags=["Identity"])
AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


@router.post(
    "/login",
    response_model=SuccessResponse[AuthenticationResult],
    status_code=status.HTTP_200_OK,
    summary="Authenticate identity user",
    description=(
        "Validates identity user credentials and returns authentication context. "
        "This endpoint does not generate JWTs, refresh tokens, or OAuth artifacts."
    ),
    responses={
        HTTPStatus.OK: {
            "description": "User authenticated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "User authenticated successfully",
                        "data": {
                            "user_id": "018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4",
                            "email": "owner@example.com",
                            "roles": ["member"],
                            "permissions": ["identity.users.read"],
                        },
                    }
                }
            },
        },
        HTTPStatus.BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Request validation failed.",
        },
        HTTPStatus.UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Invalid credentials.",
        },
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Email not verified or account disabled.",
        },
        HTTPStatus.LOCKED: {
            "model": ErrorResponse,
            "description": "Account is locked.",
        },
        HTTPStatus.INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error.",
        },
    },
)
async def login(
    request: LoginRequest,
    authentication_service: AuthenticationServiceDependency,
) -> SuccessResponse[AuthenticationResult]:
    """Authenticate an identity user."""
    result = await authentication_service.authenticate(request)
    return SuccessResponse(
        success=True,
        message="User authenticated successfully",
        data=result,
    )
