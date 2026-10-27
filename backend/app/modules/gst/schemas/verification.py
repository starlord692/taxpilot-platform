"""Pydantic schemas for GSTIN verification evidence persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.gst.evidence import GSTINEvidenceStatus
from app.modules.gst.schemas.validators import validate_gstin


class GSTINVerificationCreate(BaseModel):
    """Request schema for creating an initial GSTIN verification record."""

    model_config = ConfigDict(extra="forbid")

    gstin: str = Field(
        ...,
        description="15-character Indian GSTIN.",
        examples=["29ABCDE1234F1Z5"],
    )
    customer_id: uuid.UUID | None = Field(
        default=None,
        description="Optional associated customer UUID within the same business.",
    )
    legal_name: str | None = Field(
        default=None,
        max_length=255,
        description="Legal entity name if provided by source.",
    )
    trade_name: str | None = Field(
        default=None,
        max_length=255,
        description="Trade name if provided by source.",
    )
    registration_status: str | None = Field(
        default=None,
        max_length=50,
        description="Registration status reported by source (e.g. Active, Cancelled).",
    )
    evidence_source: str | None = Field(
        default=None,
        max_length=100,
        description="Independent evidence source identifier.",
    )
    verified_at: datetime | None = Field(
        default=None,
        description="Timestamp when verification occurred.",
    )
    raw_payload_hash: str | None = Field(
        default=None,
        max_length=64,
        description="SHA-256 hash of raw provider response payload.",
    )
    evidence_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured verification payload metadata.",
    )

    @field_validator("gstin")
    @classmethod
    def check_gstin_format(cls, value: str) -> str:
        """Validate structural GSTIN regex syntax."""
        return validate_gstin(value)


class GSTINVerificationUpdate(BaseModel):
    """Schema for updating persistent verification evidence fields."""

    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = None
    legal_name: str | None = Field(default=None, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    registration_status: str | None = Field(default=None, max_length=50)
    evidence_source: str | None = Field(default=None, max_length=100)
    verified_at: datetime | None = None
    raw_payload_hash: str | None = Field(default=None, max_length=64)
    evidence_metadata: dict[str, Any] | None = None


class GSTINVerificationStatusUpdate(BaseModel):
    """Schema for updating the evidence lifecycle status."""

    model_config = ConfigDict(extra="forbid")

    status: GSTINEvidenceStatus
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Audit reason for status change or invalidation.",
    )


class GSTINVerificationResponse(BaseModel):
    """Explicit response boundary for GSTIN verification evidence."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    gstin: str
    status: GSTINEvidenceStatus
    legal_name: str | None = None
    trade_name: str | None = None
    registration_status: str | None = None
    evidence_source: str | None = None
    verified_at: datetime | None = None
    raw_payload_hash: str | None = None
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
