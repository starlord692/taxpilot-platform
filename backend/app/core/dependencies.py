"""Reusable FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async for session in get_db_session():
        yield session
