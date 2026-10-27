"""Read-only Business Understanding response models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UnderstandingFactName = Literal["total_revenue", "total_expenses", "net_profit"]
UnderstandingSource = Literal["ACCOUNTING_PROFIT_AND_LOSS"]
UnderstandingClassification = Literal["SYSTEM_CALCULATION"]


class BusinessUnderstandingFact(BaseModel):
    """One deterministic fact exposed by the Business Understanding view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: UnderstandingFactName = Field(description="Canonical fact name.")
    value: Decimal = Field(description="Value produced by the source statement.")
    source: UnderstandingSource = Field(
        description="Authoritative bounded-context source of the fact."
    )
    classification: UnderstandingClassification = Field(
        description="Whether the value is a source fact or system calculation."
    )


class BusinessUnderstandingResponse(BaseModel):
    """Current, read-only understanding snapshot for one business."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID = Field(description="Business UUID scope.")
    generated_at: datetime = Field(
        description="Generation time supplied by the Accounting statement."
    )
    facts: tuple[BusinessUnderstandingFact, ...] = Field(
        description="Deterministically ordered Accounting facts."
    )
    limitations: tuple[str, ...] = Field(
        description="Known limitations attached to this current-state view."
    )
