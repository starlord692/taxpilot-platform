"""Assistant conversation memory policies."""

from datetime import UTC, datetime, timedelta

CONTEXT_VERSION = "assistant-context-v1"
SUMMARY_VERSION = "assistant-summary-v1"
CONTEXT_SNAPSHOT_TTL_HOURS = 24
ENTITY_REFERENCE_TTL_HOURS = 24
WORKFLOW_TTL_HOURS = 8
RECENT_MESSAGE_LIMIT = 20
RECENT_TOOL_OUTPUT_LIMIT = 5
SUMMARY_MESSAGE_THRESHOLD = 8
MAX_CONTEXT_BLOCK_CHARS = 6000


def expires_in_hours(hours: int) -> datetime:
    """Return a timezone-aware expiration timestamp."""
    return datetime.now(tz=UTC) + timedelta(hours=hours)
