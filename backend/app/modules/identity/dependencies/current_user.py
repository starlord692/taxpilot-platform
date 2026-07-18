"""Current authenticated identity user dependency."""

from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.identity.exceptions import AuthenticationRequiredException
from app.modules.identity.models import IdentityUser

bearer_scheme = HTTPBearer(
    scheme_name="Bearer Authentication",
    description="JWT access token issued by the identity session endpoint.",
    auto_error=False,
)


async def get_current_user(
    request: Request,
    _credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> IdentityUser:
    """Return the authenticated user attached by authentication middleware."""
    user = getattr(request.state, "user", None)
    if not isinstance(user, IdentityUser):
        raise AuthenticationRequiredException("Authentication required")
    return user


CurrentUser = Annotated[IdentityUser, Depends(get_current_user)]
