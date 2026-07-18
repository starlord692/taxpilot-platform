"""Identity token service."""

import hashlib
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from jose import ExpiredSignatureError, JWTError, jwt  # type: ignore[import-untyped]

from app.common.models.abstract.timestamp import utc_now
from app.core.config import Settings
from app.modules.identity.exceptions import (
    TokenConfigurationException,
    TokenExpiredException,
    TokenInvalidException,
    TokenRevokedException,
)
from app.modules.identity.models import IdentityRefreshToken
from app.modules.identity.services.authentication_service import AuthenticationResult

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 48


@dataclass(frozen=True)
class AccessTokenClaims:
    """Validated access token claims."""

    user_id: uuid.UUID
    email: str
    roles: list[str]
    permissions: list[str]
    issued_at: datetime
    expires_at: datetime
    token_type: str


@dataclass(frozen=True)
class RefreshTokenResult:
    """Generated opaque refresh token result."""

    token: str
    user_id: uuid.UUID
    expires_at: datetime
    token_type: str = REFRESH_TOKEN_TYPE


@dataclass(frozen=True)
class RefreshTokenClaims:
    """Validated refresh token state."""

    user_id: uuid.UUID
    expires_at: datetime
    token_type: str


class TokenRefreshTokenRepository(Protocol):
    """Refresh token repository behavior required by token service."""

    async def create_refresh_token(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> IdentityRefreshToken:
        """Persist a refresh token hash."""
        ...

    async def get_by_hash(self, token_hash: str) -> IdentityRefreshToken | None:
        """Return a refresh token by hash."""
        ...

    async def revoke(
        self,
        refresh_token: IdentityRefreshToken,
        *,
        revoked_at: datetime | None = None,
    ) -> IdentityRefreshToken:
        """Revoke a refresh token."""
        ...


class TokenUnitOfWork(Protocol):
    """Unit of Work contract required by token service."""

    refresh_tokens: TokenRefreshTokenRepository

    async def __aenter__(self) -> "TokenUnitOfWork":
        """Enter the token transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the token transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit token changes."""
        ...


UnitOfWorkFactory = Callable[[], TokenUnitOfWork]


class TokenService:
    """Generate, validate, revoke, and rotate identity tokens."""

    def __init__(
        self,
        *,
        settings: Settings,
        unit_of_work_factory: UnitOfWorkFactory,
    ) -> None:
        """Initialize the token service with injected dependencies."""
        self._settings = settings
        self._unit_of_work_factory = unit_of_work_factory
        self._ensure_secret_configured()

    @property
    def access_token_expires_in(self) -> int:
        """Return access token lifetime in seconds."""
        return self._settings.identity_access_token_expire_minutes * 60

    def generate_access_token(
        self,
        authentication_result: AuthenticationResult,
    ) -> str:
        """Generate a signed JWT access token from authentication context."""
        issued_at = utc_now()
        expires_at = issued_at + timedelta(
            minutes=self._settings.identity_access_token_expire_minutes
        )
        payload: dict[str, Any] = {
            "sub": str(authentication_result.user_id),
            "email": authentication_result.email,
            "roles": authentication_result.roles,
            "permissions": authentication_result.permissions,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "token_type": ACCESS_TOKEN_TYPE,
        }
        token: str = jwt.encode(
            payload,
            self._settings.identity_token_secret_key,
            algorithm=JWT_ALGORITHM,
        )
        return token

    async def generate_refresh_token(
        self,
        authentication_result: AuthenticationResult,
    ) -> RefreshTokenResult:
        """Generate and persist a hashed opaque refresh token."""
        return await self._create_refresh_token(authentication_result.user_id)

    def validate_access_token(self, token: str) -> AccessTokenClaims:
        """Validate a JWT access token and return typed claims."""
        payload = self._decode_access_token(token)
        if payload.get("token_type") != ACCESS_TOKEN_TYPE:
            raise TokenInvalidException("Invalid access token")

        try:
            return AccessTokenClaims(
                user_id=uuid.UUID(str(payload["sub"])),
                email=str(payload["email"]),
                roles=self._list_claim(payload.get("roles")),
                permissions=self._list_claim(payload.get("permissions")),
                issued_at=self._datetime_claim(payload["issued_at"]),
                expires_at=self._datetime_claim(payload["expires_at"]),
                token_type=str(payload["token_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenInvalidException("Invalid access token") from exc

    async def validate_refresh_token(self, token: str) -> RefreshTokenClaims:
        """Validate an opaque refresh token against persisted state."""
        stored_token = await self._get_valid_refresh_token(token)
        return RefreshTokenClaims(
            user_id=stored_token.user_id,
            expires_at=stored_token.expires_at,
            token_type=REFRESH_TOKEN_TYPE,
        )

    async def revoke_refresh_token(self, token: str) -> None:
        """Revoke a persisted refresh token."""
        token_hash = self._hash_refresh_token(token)
        async with self._unit_of_work_factory() as uow:
            stored_token = await uow.refresh_tokens.get_by_hash(token_hash)
            if stored_token is None:
                raise TokenInvalidException("Invalid refresh token")
            if stored_token.revoked_at is not None:
                raise TokenRevokedException("Refresh token has been revoked")
            await uow.refresh_tokens.revoke(stored_token)
            await uow.commit()

    async def rotate_refresh_token(self, refresh_token: str) -> RefreshTokenResult:
        """Revoke a valid refresh token and issue a new one for the same user."""
        token_hash = self._hash_refresh_token(refresh_token)
        async with self._unit_of_work_factory() as uow:
            stored_token = await self._get_valid_refresh_token_from_uow(
                uow,
                token_hash,
            )
            await uow.refresh_tokens.revoke(stored_token)
            new_token = self._generate_secure_refresh_token()
            expires_at = self._refresh_expires_at()
            await uow.refresh_tokens.create_refresh_token(
                user_id=stored_token.user_id,
                token_hash=self._hash_refresh_token(new_token),
                expires_at=expires_at,
            )
            await uow.commit()

        return RefreshTokenResult(
            token=new_token,
            user_id=stored_token.user_id,
            expires_at=expires_at,
        )

    async def _create_refresh_token(self, user_id: uuid.UUID) -> RefreshTokenResult:
        """Create and persist an opaque refresh token for a user."""
        token = self._generate_secure_refresh_token()
        expires_at = self._refresh_expires_at()
        async with self._unit_of_work_factory() as uow:
            await uow.refresh_tokens.create_refresh_token(
                user_id=user_id,
                token_hash=self._hash_refresh_token(token),
                expires_at=expires_at,
            )
            await uow.commit()

        return RefreshTokenResult(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
        )

    async def _get_valid_refresh_token(
        self,
        token: str,
    ) -> IdentityRefreshToken:
        """Return a valid persisted refresh token for a raw token value."""
        token_hash = self._hash_refresh_token(token)
        async with self._unit_of_work_factory() as uow:
            return await self._get_valid_refresh_token_from_uow(uow, token_hash)

    async def _get_valid_refresh_token_from_uow(
        self,
        uow: TokenUnitOfWork,
        token_hash: str,
    ) -> IdentityRefreshToken:
        """Return valid refresh token state inside an existing UoW."""
        stored_token = await uow.refresh_tokens.get_by_hash(token_hash)
        if stored_token is None:
            raise TokenInvalidException("Invalid refresh token")
        if stored_token.revoked_at is not None:
            raise TokenRevokedException("Refresh token has been revoked")
        if stored_token.expires_at <= utc_now():
            raise TokenExpiredException("Refresh token has expired")
        return stored_token

    def _decode_access_token(self, token: str) -> dict[str, Any]:
        """Decode a JWT access token and map jose errors."""
        try:
            payload = jwt.decode(
                token,
                self._settings.identity_token_secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except ExpiredSignatureError as exc:
            raise TokenExpiredException("Access token has expired") from exc
        except JWTError as exc:
            raise TokenInvalidException("Invalid access token") from exc

        if not isinstance(payload, dict):
            raise TokenInvalidException("Invalid access token")
        return payload

    def _ensure_secret_configured(self) -> None:
        """Ensure token signing is configured explicitly."""
        if not self._settings.identity_token_secret_key:
            raise TokenConfigurationException("Token secret key is not configured")

    def _refresh_expires_at(self) -> datetime:
        """Return the refresh token expiry timestamp."""
        return utc_now() + timedelta(
            days=self._settings.identity_refresh_token_expire_days
        )

    def _generate_secure_refresh_token(self) -> str:
        """Generate a secure opaque refresh token."""
        return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)

    def _hash_refresh_token(self, token: str) -> str:
        """Hash an opaque refresh token for storage and lookup."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _datetime_claim(self, value: object) -> datetime:
        """Parse a timezone-aware datetime claim."""
        if not isinstance(value, str):
            raise ValueError("Datetime claim must be a string")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _list_claim(self, value: object) -> list[str]:
        """Return a list of strings from a JWT claim."""
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError("Claim must be a list of strings")
        return value
