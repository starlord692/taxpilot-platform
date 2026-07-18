"""Identity middleware package."""

from app.modules.identity.middleware.authentication import AuthenticationMiddleware

__all__ = ["AuthenticationMiddleware"]
