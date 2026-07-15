"""Identity request schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.identity.models.enums import UserStatus
from app.modules.identity.validators import (
    normalize_and_validate_email,
    validate_password_strength,
    validate_person_name,
)


class CreateUserRequest(BaseModel):
    """Request schema for creating an identity user."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        description="Unique user email address.",
        examples=["owner@example.com"],
    )
    first_name: str = Field(
        description="User first name.",
        examples=["Jane"],
        max_length=100,
    )
    last_name: str = Field(
        description="User last name.",
        examples=["Doe"],
        max_length=100,
    )
    display_name: str | None = Field(
        default=None,
        description="Display name shown in the product.",
        examples=["Jane Doe"],
        max_length=150,
    )
    password: str = Field(
        description="Plain password accepted only in create requests.",
        examples=["StrongPassword123!"],
        min_length=12,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and normalize email."""
        return normalize_and_validate_email(email)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, first_name: str) -> str:
        """Validate first name."""
        return validate_person_name(first_name, field_name="first_name", max_length=100)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, last_name: str) -> str:
        """Validate last name."""
        return validate_person_name(last_name, field_name="last_name", max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, display_name: str | None) -> str | None:
        """Validate display name when provided."""
        if display_name is None:
            return None
        return validate_person_name(
            display_name,
            field_name="display_name",
            max_length=150,
        )

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        """Validate password strength."""
        return validate_password_strength(password)


class UpdateUserRequest(BaseModel):
    """Request schema for updating identity user profile fields."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(
        default=None,
        description="Updated user first name.",
        examples=["Jane"],
        max_length=100,
    )
    last_name: str | None = Field(
        default=None,
        description="Updated user last name.",
        examples=["Doe"],
        max_length=100,
    )
    display_name: str | None = Field(
        default=None,
        description="Updated product display name.",
        examples=["Jane Doe"],
        max_length=150,
    )
    status: UserStatus | None = Field(
        default=None,
        description="Updated identity user status.",
        examples=[UserStatus.ACTIVE],
    )

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, first_name: str | None) -> str | None:
        """Validate first name when provided."""
        if first_name is None:
            return None
        return validate_person_name(first_name, field_name="first_name", max_length=100)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, last_name: str | None) -> str | None:
        """Validate last name when provided."""
        if last_name is None:
            return None
        return validate_person_name(last_name, field_name="last_name", max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, display_name: str | None) -> str | None:
        """Validate display name when provided."""
        if display_name is None:
            return None
        return validate_person_name(
            display_name,
            field_name="display_name",
            max_length=150,
        )


class LoginRequest(BaseModel):
    """Request schema for login credential submission."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        description="User email address.",
        examples=["owner@example.com"],
    )
    password: str = Field(
        description="Plain password accepted only in login requests.",
        examples=["StrongPassword123!"],
        min_length=1,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and normalize email."""
        return normalize_and_validate_email(email)


class AssignRoleRequest(BaseModel):
    """Request schema for assigning a role to a user."""

    model_config = ConfigDict(extra="forbid")

    role_id: uuid.UUID = Field(
        description="Role UUID to assign.",
        examples=["018f1d3c-4f87-7b6f-8f25-6cfcdd17f8b4"],
    )
