"""Tests for identity token service."""

import uuid
from datetime import datetime
from typing import Self

import pytest

from app.common.models.abstract.timestamp import utc_now
from app.core.config import Settings
from app.modules.identity.exceptions import (
    TokenExpiredException,
    TokenInvalidException,
    TokenRevokedException,
)
from app.modules.identity.models import IdentityRefreshToken
from app.modules.identity.services import AuthenticationResult
from app.modules.identity.services.token_service import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    RefreshTokenResult,
    TokenRefreshTokenRepository,
    TokenService,
)

ROTATED_TOKEN_COUNT = 2


class FakeRefreshTokenRepository:
    """In-memory refresh token repository for token service tests."""

    def __init__(self) -> None:
        """Initialize empty token storage."""
        self.tokens: dict[str, IdentityRefreshToken] = {}

    async def create_refresh_token(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> IdentityRefreshToken:
        """Store a refresh token hash."""
        token = IdentityRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.tokens[token_hash] = token
        return token

    async def get_by_hash(self, token_hash: str) -> IdentityRefreshToken | None:
        """Return a token by hash."""
        return self.tokens.get(token_hash)

    async def revoke(
        self,
        refresh_token: IdentityRefreshToken,
        *,
        revoked_at: datetime | None = None,
    ) -> IdentityRefreshToken:
        """Revoke a refresh token."""
        refresh_token.revoked_at = revoked_at or utc_now()
        return refresh_token


class FakeTokenUnitOfWork:
    """Fake Unit of Work for token service tests."""

    def __init__(self, repository: FakeRefreshTokenRepository) -> None:
        """Initialize with shared token storage."""
        self.refresh_tokens: TokenRefreshTokenRepository = repository
        self.commits = 0

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""

    async def commit(self) -> None:
        """Record a commit."""
        self.commits += 1


def build_authentication_result() -> AuthenticationResult:
    """Build a valid authentication result."""
    return AuthenticationResult(
        user_id=uuid.uuid4(),
        email="owner@example.com",
        roles=["member"],
        permissions=["identity.users.read"],
    )


def build_settings(
    *,
    identity_token_secret_key: str = "test-secret-key",
    identity_access_token_expire_minutes: int = 15,
    identity_refresh_token_expire_days: int = 30,
) -> Settings:
    """Build token service settings."""
    return Settings(
        identity_token_secret_key=identity_token_secret_key,
        identity_access_token_expire_minutes=identity_access_token_expire_minutes,
        identity_refresh_token_expire_days=identity_refresh_token_expire_days,
    )


def build_service(
    repository: FakeRefreshTokenRepository,
    *,
    settings: Settings | None = None,
) -> TokenService:
    """Build a token service using fake persistence."""
    return TokenService(
        settings=settings or build_settings(),
        unit_of_work_factory=lambda: FakeTokenUnitOfWork(repository),
    )


def test_access_token_generation_and_validation() -> None:
    """Access tokens include and validate authentication claims."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    authentication_result = build_authentication_result()

    token = service.generate_access_token(authentication_result)
    claims = service.validate_access_token(token)

    assert claims.user_id == authentication_result.user_id
    assert claims.email == authentication_result.email
    assert claims.roles == ["member"]
    assert claims.permissions == ["identity.users.read"]
    assert claims.token_type == ACCESS_TOKEN_TYPE


@pytest.mark.asyncio
async def test_refresh_token_generation_hashes_stored_token() -> None:
    """Refresh tokens are opaque and only their hashes are persisted."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    authentication_result = build_authentication_result()

    result = await service.generate_refresh_token(authentication_result)

    assert isinstance(result, RefreshTokenResult)
    assert result.user_id == authentication_result.user_id
    assert result.token_type == REFRESH_TOKEN_TYPE
    assert result.token not in repository.tokens
    assert len(repository.tokens) == 1
    stored_token = next(iter(repository.tokens.values()))
    assert stored_token.token_hash != result.token


@pytest.mark.asyncio
async def test_refresh_token_validation() -> None:
    """Refresh token validation returns persisted token state."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    authentication_result = build_authentication_result()
    refresh_token = await service.generate_refresh_token(authentication_result)

    claims = await service.validate_refresh_token(refresh_token.token)

    assert claims.user_id == authentication_result.user_id
    assert claims.token_type == REFRESH_TOKEN_TYPE


def test_expired_access_token_raises() -> None:
    """Expired access tokens are rejected."""
    repository = FakeRefreshTokenRepository()
    service = build_service(
        repository,
        settings=build_settings(identity_access_token_expire_minutes=-1),
    )
    token = service.generate_access_token(build_authentication_result())

    with pytest.raises(TokenExpiredException):
        service.validate_access_token(token)


def test_invalid_access_token_signature_raises() -> None:
    """Access tokens signed with a different secret are rejected."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    other_service = build_service(
        repository,
        settings=build_settings(identity_token_secret_key="other-secret-key"),
    )
    token = other_service.generate_access_token(build_authentication_result())

    with pytest.raises(TokenInvalidException):
        service.validate_access_token(token)


@pytest.mark.asyncio
async def test_revoked_refresh_token_raises() -> None:
    """Revoked refresh tokens are rejected."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    refresh_token = await service.generate_refresh_token(build_authentication_result())

    await service.revoke_refresh_token(refresh_token.token)

    with pytest.raises(TokenRevokedException):
        await service.validate_refresh_token(refresh_token.token)


@pytest.mark.asyncio
async def test_expired_refresh_token_raises() -> None:
    """Expired refresh tokens are rejected."""
    repository = FakeRefreshTokenRepository()
    service = build_service(
        repository,
        settings=build_settings(identity_refresh_token_expire_days=-1),
    )
    refresh_token = await service.generate_refresh_token(build_authentication_result())

    with pytest.raises(TokenExpiredException):
        await service.validate_refresh_token(refresh_token.token)


@pytest.mark.asyncio
async def test_refresh_token_rotation_revokes_old_and_creates_new() -> None:
    """Refresh token rotation revokes the old token and issues a new one."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)
    refresh_token = await service.generate_refresh_token(build_authentication_result())

    rotated_token = await service.rotate_refresh_token(refresh_token.token)

    assert rotated_token.token != refresh_token.token
    assert rotated_token.user_id == refresh_token.user_id
    assert len(repository.tokens) == ROTATED_TOKEN_COUNT
    with pytest.raises(TokenRevokedException):
        await service.validate_refresh_token(refresh_token.token)
    rotated_claims = await service.validate_refresh_token(rotated_token.token)
    assert rotated_claims.user_id == refresh_token.user_id


@pytest.mark.asyncio
async def test_malformed_refresh_token_raises() -> None:
    """Unknown opaque refresh tokens are rejected."""
    repository = FakeRefreshTokenRepository()
    service = build_service(repository)

    with pytest.raises(TokenInvalidException):
        await service.validate_refresh_token("not-a-known-token")
