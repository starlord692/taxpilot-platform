"""Identity API package."""

from app.modules.identity.api.login_router import router as login_router
from app.modules.identity.api.router import router

__all__ = ["login_router", "router"]
