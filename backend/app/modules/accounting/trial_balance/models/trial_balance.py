"""Trial Balance read models."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TrialBalanceAccount(BaseModel):
    """One account row in a Trial Balance."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID = Field(description="Account UUID.")
    account_code: str = Field(description="Account code.")
    account_name: str = Field(description="Account name.")
    account_type: str = Field(description="Account type name.")
    account_category: str = Field(description="Account category name.")
    debit: Decimal = Field(description="Debit presentation amount.")
    credit: Decimal = Field(description="Credit presentation amount.")
    balance: Decimal = Field(description="Net account balance.")


class TrialBalance(BaseModel):
    """Trial Balance generated from account balance read models."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    generated_at: datetime = Field(description="Timezone-aware generation time.")
    total_debit: Decimal = Field(description="Total debit amount.")
    total_credit: Decimal = Field(description="Total credit amount.")
    is_balanced: bool = Field(description="Whether debit and credit totals match.")
    accounts: list[TrialBalanceAccount] = Field(
        description="Accounts included in the Trial Balance."
    )
