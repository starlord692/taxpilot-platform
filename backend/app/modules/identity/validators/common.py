"""Reusable identity schema validators."""

import re

EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9]")
MAX_EMAIL_LENGTH = 320
MIN_PASSWORD_LENGTH = 12


def normalize_and_validate_email(email: str) -> str:
    """Validate and lowercase-normalize an email address."""
    normalized = email.strip().lower()
    if (
        len(normalized) > MAX_EMAIL_LENGTH
        or EMAIL_PATTERN.fullmatch(normalized) is None
    ):
        raise ValueError("Invalid email address")
    return normalized


def validate_password_strength(password: str) -> str:
    """Validate password strength for identity requests."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Password must be at least 12 characters long")
    if not any(character.isupper() for character in password):
        raise ValueError("Password must contain an uppercase letter")
    if not any(character.islower() for character in password):
        raise ValueError("Password must contain a lowercase letter")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must contain a digit")
    if SPECIAL_CHARACTER_PATTERN.search(password) is None:
        raise ValueError("Password must contain a special character")
    return password


def validate_person_name(value: str, *, field_name: str, max_length: int) -> str:
    """Validate a human-readable identity name field."""
    normalized = " ".join(value.strip().split())
    if len(normalized) < 1:
        raise ValueError(f"{field_name} is required")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized
