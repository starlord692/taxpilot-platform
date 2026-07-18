"""Financial statement read models."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StatementLine(BaseModel):
    """One financial statement line."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID = Field(description="Account UUID.")
    account_code: str = Field(description="Account code.")
    account_name: str = Field(description="Account name.")
    account_type: str = Field(description="Account type name.")
    amount: Decimal = Field(description="Statement amount.")


class ProfitAndLossStatement(BaseModel):
    """Profit and Loss Statement generated from Trial Balance."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    generated_at: datetime = Field(description="Timezone-aware generation time.")
    revenue: list[StatementLine] = Field(description="Revenue statement lines.")
    expenses: list[StatementLine] = Field(description="Expense statement lines.")
    total_revenue: Decimal = Field(description="Total revenue.")
    total_expenses: Decimal = Field(description="Total expenses.")
    net_profit: Decimal = Field(description="Net profit or loss.")


class BalanceSheet(BaseModel):
    """Balance Sheet generated from Trial Balance."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    generated_at: datetime = Field(description="Timezone-aware generation time.")
    assets: list[StatementLine] = Field(description="Asset statement lines.")
    liabilities: list[StatementLine] = Field(
        description="Liability statement lines."
    )
    equity: list[StatementLine] = Field(description="Equity statement lines.")
    total_assets: Decimal = Field(description="Total assets.")
    total_liabilities: Decimal = Field(description="Total liabilities.")
    total_equity: Decimal = Field(description="Total equity.")
    is_balanced: bool = Field(description="Whether the Balance Sheet balances.")
