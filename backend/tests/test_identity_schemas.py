"""Tests for identity Pydantic schemas."""

import uuid

import pytest
from pydantic import ValidationError

from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.identity.schemas import (
    AssignRoleRequest,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    RoleResponse,
    UpdateUserRequest,
    UserResponse,
)


def test_create_user_rejects_invalid_email() -> None:
    """Create user request rejects invalid email addresses."""
    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="not-an-email",
            first_name="Jane",
            last_name="Doe",
            display_name="Jane Doe",
            password="StrongPassword123!",
        )


def test_create_user_rejects_weak_password() -> None:
    """Create user request rejects weak passwords."""
    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="owner@example.com",
            first_name="Jane",
            last_name="Doe",
            display_name="Jane Doe",
            password="weak",
        )


def test_assign_role_rejects_invalid_uuid() -> None:
    """Assign role request validates UUID input."""
    with pytest.raises(ValidationError):
        AssignRoleRequest(role_id="not-a-uuid")


def test_update_user_rejects_invalid_status_enum() -> None:
    """Update user request validates status enum values."""
    with pytest.raises(ValidationError):
        UpdateUserRequest(status="unknown")


def test_login_request_normalizes_email() -> None:
    """Login request validates and normalizes email input."""
    request = LoginRequest(email="OWNER@EXAMPLE.COM", password="secret")

    assert request.email == "owner@example.com"


def test_user_response_serializes_from_orm_model() -> None:
    """User response supports ORM serialization without audit fields."""
    user = IdentityUser(
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )
    user.id = uuid.uuid4()

    response = UserResponse.model_validate(user)
    payload = response.model_dump()

    assert payload["id"] == user.id
    assert payload["email"] == "owner@example.com"
    assert payload["status"] == UserStatus.ACTIVE
    assert "password_hash" not in payload
    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "created_by" not in payload
    assert "updated_by" not in payload


def test_response_models_do_not_define_password_hash() -> None:
    """Identity response schemas never expose password hashes."""
    response_models = (UserResponse, RoleResponse, LoginResponse)

    for response_model in response_models:
        assert "password_hash" not in response_model.model_fields
        assert "password" not in response_model.model_fields
