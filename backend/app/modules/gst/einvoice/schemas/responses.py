"""E-invoicing response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.gst.einvoice.models import (
    EInvoiceStatus,
    EWayBillStatus,
    GSTProviderType,
    TransportMode,
)


class EInvoiceResponse(BaseModel):
    """Response schema for an e-invoice."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="E-invoice UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    invoice_id: uuid.UUID = Field(description="Sales invoice UUID.")
    irn: str = Field(description="Invoice Reference Number.")
    ack_number: str = Field(description="Provider acknowledgement number.")
    ack_date: datetime = Field(description="Provider acknowledgement timestamp.")
    status: EInvoiceStatus = Field(description="E-invoice status.")
    provider_name: str = Field(description="GST provider name.")
    request_payload: dict[str, Any] = Field(description="Provider request payload.")
    response_payload: dict[str, Any] = Field(description="Provider response payload.")
    cancel_reason: str | None = Field(
        default=None,
        description="Cancellation reason.",
    )
    cancelled_at: datetime | None = Field(
        default=None,
        description="Cancellation timestamp.",
    )


class EInvoiceQRCodeResponse(BaseModel):
    """Response schema for e-invoice QR code data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="QR code record UUID.")
    invoice_id: uuid.UUID = Field(description="Sales invoice UUID.")
    qr_content: str = Field(description="QR payload content.")
    hash_value: str = Field(description="QR payload hash.")


class EWayBillResponse(BaseModel):
    """Response schema for an e-way bill."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="E-way bill UUID.")
    invoice_id: uuid.UUID = Field(description="Sales invoice UUID.")
    eway_bill_number: str = Field(description="E-way bill number.")
    valid_from: datetime = Field(description="Validity start timestamp.")
    valid_to: datetime = Field(description="Validity end timestamp.")
    vehicle_number: str | None = Field(default=None, description="Vehicle number.")
    transport_mode: TransportMode = Field(description="Transport mode.")
    status: EWayBillStatus = Field(description="E-way bill status.")
    cancel_reason: str | None = Field(
        default=None,
        description="Cancellation reason.",
    )
    cancelled_at: datetime | None = Field(
        default=None,
        description="Cancellation timestamp.",
    )


class GSTProviderResponse(BaseModel):
    """Response schema for a configured GST provider."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Provider UUID.")
    name: str = Field(description="Provider name.")
    base_url: str = Field(description="Provider base URL.")
    provider_type: GSTProviderType = Field(description="Provider type.")
    is_active: bool = Field(description="Whether provider is active.")


class EInvoiceStatusResponse(BaseModel):
    """Combined status response for e-invoice and e-way bill records."""

    e_invoice: EInvoiceResponse | None = Field(
        default=None,
        description="E-invoice record when available.",
    )
    qr_code: EInvoiceQRCodeResponse | None = Field(
        default=None,
        description="QR code record when available.",
    )
    eway_bill: EWayBillResponse | None = Field(
        default=None,
        description="E-way bill record when available.",
    )
    provider_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider status payload.",
    )
