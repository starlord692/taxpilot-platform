"""Identity dependency package."""

from app.modules.identity.dependencies.current_user import CurrentUser, get_current_user

__all__ = ["CurrentUser", "get_current_user"]
