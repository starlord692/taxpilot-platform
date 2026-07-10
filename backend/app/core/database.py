"""SQLAlchemy database configuration."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from app.core.config import Settings, get_settings


class DatabaseState:
    """Container for database connection state."""

    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None


database_state = DatabaseState()


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for future SQLAlchemy ORM models."""


def initialize_database(settings: Settings | None = None) -> None:
    """Initialize the async SQLAlchemy engine and session factory."""
    active_settings = settings or get_settings()
    if (
        database_state.engine is not None
        and database_state.session_factory is not None
    ):
        return

    database_state.engine = create_async_engine(
        active_settings.database_url,
        echo=active_settings.database_echo,
        pool_size=active_settings.database_pool_size,
        max_overflow=active_settings.database_max_overflow,
        pool_pre_ping=True,
    )
    database_state.session_factory = async_sessionmaker(
        bind=database_state.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for FastAPI dependency injection."""
    if database_state.session_factory is None:
        initialize_database()

    if database_state.session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

    async with database_state.session_factory() as session:
        yield session


async def dispose_database() -> None:
    """Dispose database engine connections."""
    if database_state.engine is not None:
        await database_state.engine.dispose()

    database_state.engine = None
    database_state.session_factory = None
