"""E-invoicing request schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.gst.einvoice.models import TransportMode


class EInvoiceGenerateRequest(BaseModel):
    """Request to generate an IRN for a posted sales invoice."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID = Field(
        ...,
        description="Sales invoice UUID.",
        examples=["0190b812-8b56-7458-a9f2-7df0d2a73a50"],
    )
    provider_name: str = Field(
        default="mock",
        min_length=2,
        max_length=100,
        description="Configured GST provider name.",
        examples=["mock"],
    )
    generate_eway_bill: bool = Field(
        default=False,
        description="Whether to generate an e-way bill after IRN generation.",
        examples=[False],
    )
    vehicle_number: str | None = Field(
        default=None,
        max_length=20,
        description="Vehicle number when e-way bill generation is requested.",
        examples=["KA01AB1234"],
    )
    transport_mode: TransportMode = Field(
        default=TransportMode.ROAD,
        description="Transport mode for e-way bill generation.",
        examples=[TransportMode.ROAD],
    )


class EInvoiceCancelRequest(BaseModel):
    """Request to cancel an IRN."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID = Field(
        ...,
        description="Sales invoice UUID.",
        examples=["0190b812-8b56-7458-a9f2-7df0d2a73a50"],
    )
    reason: str = Field(
        ...,
        min_length=3,
        max_length=250,
        description="Cancellation reason.",
        examples=["Invoice cancelled by customer"],
    )


class EWayBillGenerateRequest(BaseModel):
    """Request to generate an e-way bill."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID = Field(
        ...,
        description="Sales invoice UUID.",
        examples=["0190b812-8b56-7458-a9f2-7df0d2a73a50"],
    )
    provider_name: str = Field(
        default="mock",
        min_length=2,
        max_length=100,
        description="Configured GST provider name.",
        examples=["mock"],
    )
    vehicle_number: str | None = Field(
        default=None,
        max_length=20,
        description="Vehicle number.",
        examples=["KA01AB1234"],
    )
    transport_mode: TransportMode = Field(
        default=TransportMode.ROAD,
        description="Transport mode.",
        examples=[TransportMode.ROAD],
    )


class EWayBillCancelRequest(BaseModel):
    """Request to cancel an e-way bill."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID = Field(
        ...,
        description="Sales invoice UUID.",
        examples=["0190b812-8b56-7458-a9f2-7df0d2a73a50"],
    )
    reason: str = Field(
        ...,
        min_length=3,
        max_length=250,
        description="Cancellation reason.",
        examples=["Transport cancelled"],
    )
