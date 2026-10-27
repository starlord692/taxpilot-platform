"""Pydantic schemas for read-only accounting inspection."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    """Chart of Accounts row presentation."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(description="Account unique identifier.")
    account_code: str = Field(description="Account code.")
    account_name: str = Field(description="Account name.")
    category_name: str = Field(
        description="Top-level category name (Asset, Liability, etc.).",
    )
    account_type_name: str = Field(description="Account type name.")
    normal_balance: str = Field(
        description="Normal balance direction (debit or credit).",
    )
    current_debit: Decimal = Field(description="Current cumulative debit balance.")
    current_credit: Decimal = Field(description="Current cumulative credit balance.")
    current_balance: Decimal = Field(description="Current net account balance.")
    is_system: bool = Field(description="Whether this is a system default account.")
    is_active: bool = Field(description="Whether the account is active.")
    parent_account_id: uuid.UUID | None = Field(
        default=None,
        description="Parent account ID if nested.",
    )
    description: str | None = Field(default=None, description="Account description.")


class AccountDetailResponse(AccountResponse):
    """Detailed chart account presentation."""


class GeneralLedgerEntryResponse(BaseModel):
    """Paginated General Ledger entry presentation."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(description="Ledger entry UUID.")
    transaction_date: date = Field(description="Transaction date.")
    posting_date: date = Field(description="Posting date.")
    journal_entry_id: uuid.UUID = Field(description="Journal entry UUID.")
    journal_number: str = Field(description="Journal entry number.")
    journal_reference: str | None = Field(
        default=None,
        description="Journal reference.",
    )
    account_id: uuid.UUID = Field(description="Account UUID.")
    account_code: str = Field(description="Account code.")
    account_name: str = Field(description="Account name.")
    debit: Decimal = Field(description="Debit amount.")
    credit: Decimal = Field(description="Credit amount.")
    running_balance: Decimal | None = Field(
        default=None,
        description="Continuous running balance (single-account queries only).",
    )
    description: str | None = Field(
        default=None,
        description="Entry description.",
    )
    source_module: str | None = Field(
        default=None,
        description="Source module (sales, purchases, expenses).",
    )
    source_entity: str | None = Field(
        default=None,
        description="Source entity type.",
    )
    source_entity_id: uuid.UUID | None = Field(
        default=None,
        description="Source entity ID.",
    )
    source_document_url: str | None = Field(
        default=None,
        description="Frontend route to the source document.",
    )


class TrialBalanceAccountResponse(BaseModel):
    """One account row in a Trial Balance response."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID = Field(description="Account UUID.")
    account_code: str = Field(description="Account code.")
    account_name: str = Field(description="Account name.")
    account_category: str = Field(description="Account category name.")
    account_type: str = Field(description="Account type name.")
    normal_balance: str = Field(
        description="Normal balance direction (debit or credit).",
    )
    debit: Decimal = Field(description="Reported debit presentation amount.")
    credit: Decimal = Field(description="Reported credit presentation amount.")
    balance: Decimal = Field(description="Reported net balance.")


class TrialBalanceResponse(BaseModel):
    """Trial Balance report with equilibrium and disclosure metadata."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    generated_at: datetime = Field(description="Generation timestamp.")
    as_of_date: date = Field(description="Cutoff date for ledger balances.")
    total_debit: Decimal = Field(description="Total debits across all accounts.")
    total_credit: Decimal = Field(description="Total credits across all accounts.")
    discrepancy: Decimal = Field(
        description="Net discrepancy (total_debit - total_credit).",
    )
    is_balanced: bool = Field(
        description="Whether total debits exactly equal total credits.",
    )
    historical_mode: str = Field(description="Historical reporting mode.")
    opening_balances_present: bool = Field(
        description="Whether opening balances are present.",
    )
    fiscal_period_closed: bool = Field(
        description="Whether fiscal closing entries are present.",
    )
    reporting_limitations: list[str] = Field(
        description="Notices detailing reporting boundaries.",
    )
    accounts: list[TrialBalanceAccountResponse] = Field(
        description="List of accounts included.",
    )
