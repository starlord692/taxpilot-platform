"""Authentication middleware for identity access tokens."""

import uuid
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.common.exceptions import TaxPilotException
from app.core.database import database_state, initialize_database
from app.core.responses import ErrorDetail, ErrorResponse
from app.modules.identity.api.dependencies import get_token_service
from app.modules.identity.exceptions import (
    AuthenticationAccountDisabledException,
    AuthenticationRequiredException,
    AuthenticationUserUnavailableException,
)
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.identity.repository import IdentityUserRepository
from app.modules.identity.services import TokenService

TokenServiceFactory = Callable[[], TokenService]
UserLoader = Callable[[Request, uuid.UUID], Awaitable[IdentityUser | None]]
BEARER_AUTHORIZATION_PARTS = 2


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authenticate bearer tokens and attach users to request state."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Authenticate the request when an Authorization header is present."""
        authorization = request.headers.get("authorization")
        if authorization is None:
            return await call_next(request)

        try:
            token = self._extract_bearer_token(authorization)
            token_service = self._get_token_service(request)
            claims = token_service.validate_access_token(token)
            user = await self._load_user(request, claims.user_id)
            self._ensure_user_is_available(user)
        except TaxPilotException as exc:
            return self._error_response(exc)

        request.state.user = user
        request.state.token_claims = claims
        return await call_next(request)

    def _extract_bearer_token(self, authorization: str) -> str:
        """Extract a bearer token from the Authorization header."""
        parts = authorization.split()
        if (
            len(parts) != BEARER_AUTHORIZATION_PARTS
            or parts[0].lower() != "bearer"
            or not parts[1]
        ):
            raise AuthenticationRequiredException(
                "Missing or malformed Authorization header"
            )
        return parts[1]

    def _get_token_service(self, request: Request) -> TokenService:
        """Return the configured token service for this request."""
        factory = getattr(
            request.app.state,
            "identity_token_service_factory",
            get_token_service,
        )
        return factory()

    async def _load_user(
        self,
        request: Request,
        user_id: uuid.UUID,
    ) -> IdentityUser | None:
        """Load the authenticated user by token subject."""
        loader = cast(
            UserLoader | None,
            getattr(request.app.state, "identity_user_loader", None),
        )
        if loader is not None:
            return await loader(request, user_id)

        if database_state.session_factory is None:
            initialize_database()
        if database_state.session_factory is None:
            raise AuthenticationUserUnavailableException(
                "Authenticated user is unavailable"
            )

        async with database_state.session_factory() as session:
            repository = IdentityUserRepository(session)
            return await repository.get_by_id(user_id)

    def _ensure_user_is_available(self, user: IdentityUser | None) -> None:
        """Reject missing, deleted, or disabled users."""
        if user is None or user.is_deleted:
            raise AuthenticationUserUnavailableException(
                "Authenticated user is unavailable"
            )
        if user.status == UserStatus.DISABLED:
            raise AuthenticationAccountDisabledException("Account is disabled")

    def _error_response(self, exc: TaxPilotException) -> JSONResponse:
        """Return standardized authentication error responses."""
        response = ErrorResponse(
            success=False,
            message=exc.message,
            data=ErrorDetail(code=exc.error_code, details=exc.details),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )
