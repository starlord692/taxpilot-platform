"""Trial Balance read models."""

import uuid
from datetime import date, datetime
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
    normal_balance: str = Field(
        default="debit",
        description="Normal balance direction (debit or credit).",
    )
    debit: Decimal = Field(description="Debit presentation amount.")
    credit: Decimal = Field(description="Credit presentation amount.")
    balance: Decimal = Field(description="Net account balance.")


class TrialBalance(BaseModel):
    """Trial Balance generated from account balances or cumulative ledger entries."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    generated_at: datetime = Field(description="Timezone-aware generation time.")
    as_of_date: date | None = Field(
        default=None,
        description="Evaluation cutoff date.",
    )
    total_debit: Decimal = Field(description="Total debit amount.")
    total_credit: Decimal = Field(description="Total credit amount.")
    discrepancy: Decimal = Field(
        default=Decimal("0.00"),
        description="Net difference between debits and credits.",
    )
    is_balanced: bool = Field(description="Whether debit and credit totals match.")
    historical_mode: str = Field(
        default="ledger_derived_cumulative",
        description="Historical calculation mode.",
    )
    opening_balances_present: bool = Field(
        default=False,
        description="Whether opening balances are present.",
    )
    fiscal_period_closed: bool = Field(
        default=False,
        description="Whether fiscal period is closed.",
    )
    reporting_limitations: list[str] = Field(
        default_factory=lambda: [
            (
                "Balances reflect cumulative ledger entries recorded in "
                "TaxPilot from inception to date."
            ),
            (
                "Pre-system opening balances are not recorded; transactions "
                "prior to system go-live are not reflected."
            ),
            (
                "Fiscal year-end closing entries are not present; revenue and "
                "expense accounts reflect inception-to-date cumulative activity."
            ),
        ],
        description="Notices detailing boundaries and missing pre-system history.",
    )
    accounts: list[TrialBalanceAccount] = Field(
        description="Accounts included in the Trial Balance."
    )
