"""Identity refresh token repository."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models.abstract.timestamp import utc_now
from app.common.repositories import BaseRepository
from app.modules.identity.models import IdentityRefreshToken


class IdentityRefreshTokenRepository(BaseRepository[IdentityRefreshToken]):
    """Repository for persisted refresh token hashes."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, IdentityRefreshToken)

    async def create_refresh_token(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> IdentityRefreshToken:
        """Persist a refresh token hash."""
        refresh_token = IdentityRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return await self.add(refresh_token)

    async def get_by_hash(self, token_hash: str) -> IdentityRefreshToken | None:
        """Return a refresh token by its stored hash."""
        statement = select(IdentityRefreshToken).where(
            IdentityRefreshToken.token_hash == token_hash,
            IdentityRefreshToken.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke(
        self,
        refresh_token: IdentityRefreshToken,
        *,
        revoked_at: datetime | None = None,
    ) -> IdentityRefreshToken:
        """Mark a refresh token as revoked."""
        refresh_token.revoked_at = revoked_at or utc_now()
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token
