"""Identity response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.models.enums import UserStatus


class IdentityResponse(BaseModel):
    """Base response schema with ORM serialization support."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class PermissionResponse(IdentityResponse):
    """Response schema for identity permissions."""

    id: uuid.UUID = Field(
        description="Permission UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    name: str = Field(
        description="Unique permission name.",
        examples=["identity.users.read"],
    )
    description: str | None = Field(
        default=None,
        description="Permission description.",
        examples=["Allows reading identity users."],
    )


class RoleResponse(IdentityResponse):
    """Response schema for identity roles."""

    id: uuid.UUID = Field(
        description="Role UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    name: str = Field(description="Unique role name.", examples=["admin"])
    description: str | None = Field(
        default=None,
        description="Role description.",
        examples=["Administrator role."],
    )
    is_system: bool = Field(
        description="Whether the role is system-managed.",
        examples=[False],
    )


class UserResponse(IdentityResponse):
    """Response schema for identity users."""

    id: uuid.UUID = Field(
        description="User UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    email: str = Field(
        description="User email address.",
        examples=["owner@example.com"],
    )
    first_name: str = Field(description="User first name.", examples=["Jane"])
    last_name: str = Field(description="User last name.", examples=["Doe"])
    display_name: str = Field(
        description="User display name.",
        examples=["Jane Doe"],
    )
    status: UserStatus = Field(
        description="Current user status.",
        examples=[UserStatus.ACTIVE],
    )
    last_login_at: datetime | None = Field(
        default=None,
        description="Last successful login timestamp.",
        examples=["2026-07-15T10:00:00+00:00"],
    )
    failed_login_attempts: int = Field(
        description="Current failed login attempt count.",
        examples=[0],
    )
    locked_until: datetime | None = Field(
        default=None,
        description="Timestamp until which the user is locked.",
        examples=["2026-07-15T10:15:00+00:00"],
    )


class LoginResponse(IdentityResponse):
    """Response schema for successful login results."""

    access_token: str = Field(
        description="Opaque access token returned by authentication.",
        examples=["access-token"],
    )
    refresh_token: str = Field(
        description="Opaque refresh token returned by authentication.",
        examples=["refresh-token"],
    )
    token_type: str = Field(
        default="bearer",
        description="Token type.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        description="Access token lifetime in seconds.",
        examples=[3600],
        gt=0,
    )


class SessionUserResponse(IdentityResponse):
    """Authenticated user context returned with a login session."""

    id: uuid.UUID = Field(
        description="Authenticated user UUID.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
    email: str = Field(
        description="Authenticated user email address.",
        examples=["owner@example.com"],
    )
    roles: list[str] = Field(
        description="Role names assigned to the authenticated user.",
        examples=[["member"]],
    )
    permissions: list[str] = Field(
        description="Permission names available to the authenticated user.",
        examples=[["identity.users.read"]],
    )


class SessionResponse(IdentityResponse):
    """Response schema for issued login sessions."""

    access_token: str = Field(
        description="Signed JWT access token.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    refresh_token: str = Field(
        description="Opaque refresh token.",
        examples=["secure-refresh-token"],
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type for Authorization headers.",
        examples=["Bearer"],
    )
    expires_in: int = Field(
        description="Access token lifetime in seconds.",
        examples=[900],
        gt=0,
    )
    user: SessionUserResponse = Field(
        description="Authenticated user context.",
    )
