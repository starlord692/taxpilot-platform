"""Identity session API router."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ErrorResponse, SuccessResponse
from app.modules.identity.api.dependencies import (
    get_authentication_service,
    get_token_service,
)
from app.modules.identity.schemas import (
    LoginRequest,
    SessionResponse,
    SessionUserResponse,
)
from app.modules.identity.services import AuthenticationService, TokenService

router = APIRouter(prefix="/identity", tags=["Identity"])
AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]
TokenServiceDependency = Annotated[
    TokenService,
    Depends(get_token_service),
]


@router.post(
    "/session",
    response_model=SuccessResponse[SessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Create identity login session",
    description=(
        "Authenticates identity user credentials and issues access and refresh "
        "tokens by orchestrating the authentication and token services."
    ),
    responses={
        HTTPStatus.OK: {
            "description": "Login session created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Login session created successfully",
                        "data": {
                            "access_token": "access-token",
                            "refresh_token": "refresh-token",
                            "token_type": "Bearer",
                            "expires_in": 900,
                            "user": {
                                "id": "018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4",
                                "email": "owner@example.com",
                                "roles": ["member"],
                                "permissions": ["identity.users.read"],
                            },
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
async def create_session(
    request: LoginRequest,
    authentication_service: AuthenticationServiceDependency,
    token_service: TokenServiceDependency,
) -> SuccessResponse[SessionResponse]:
    """Authenticate credentials and issue a login session."""
    authentication_result = await authentication_service.authenticate(request)
    access_token = token_service.generate_access_token(authentication_result)
    refresh_token = await token_service.generate_refresh_token(authentication_result)

    return SuccessResponse(
        success=True,
        message="Login session created successfully",
        data=SessionResponse(
            access_token=access_token,
            refresh_token=refresh_token.token,
            token_type="Bearer",
            expires_in=token_service.access_token_expires_in,
            user=SessionUserResponse(
                id=authentication_result.user_id,
                email=authentication_result.email,
                roles=authentication_result.roles,
                permissions=authentication_result.permissions,
            ),
        ),
    )
