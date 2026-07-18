"""Redis connection management."""

from redis.asyncio import Redis

from app.core.config import Settings, get_settings


class RedisState:
    """Container for Redis connection state."""

    client: Redis | None = None


redis_state = RedisState()


async def initialize_redis(settings: Settings | None = None) -> Redis:
    """Initialize the Redis client."""
    if redis_state.client is not None:
        return redis_state.client

    active_settings = settings or get_settings()
    redis_state.client = Redis.from_url(
        active_settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await redis_state.client.ping()
    return redis_state.client


def get_redis_client() -> Redis:
    """Return the initialized Redis client."""
    if redis_state.client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_state.client


async def close_redis() -> None:
    """Close the Redis client connection."""
    if redis_state.client is not None:
        await redis_state.client.aclose()
    redis_state.client = None
