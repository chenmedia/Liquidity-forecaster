"""Pydantic models for the subset of the Folio API the forecaster reads.

Responses are schema-validated against these before use (docs/06-security.md §8).
Only the fields the forecaster needs are modelled; unknown fields are ignored.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class AccountType(StrEnum):
    CARD = "Card"
    EARMARKS = "Earmarks"
    OPERATIONAL = "Operational"
    TAX = "Tax"
    SAVINGS = "Savings"


class PaymentState(StrEnum):
    DRAFT = "Draft"
    IN_PROCESS = "InProcess"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    RETRYING_INSUFFICIENT_FUNDS = "RetryingInsufficientFunds"


class Account(_Model):
    account_number: str = Field(alias="accountNumber")
    balance: Decimal
    balance_updated_at: datetime = Field(alias="balanceUpdatedAt")
    matching_transactions_at: datetime = Field(alias="matchingTransactionsAt")
    name: str
    type: AccountType


class AccountsResponse(_Model):
    accounts: list[Account]


class AccountBalance(_Model):
    incoming_balance: Decimal | None = Field(default=None, alias="incomingBalance")
    outgoing_balance: Decimal | None = Field(default=None, alias="outgoingBalance")


class CurrencyAmount(_Model):
    amount: Decimal
    currency: str


class Creditor(_Model):
    name: str
    account_number: str | None = Field(default=None, alias="accountNumber")


class Payment(_Model):
    id: str
    state: PaymentState
    creditor: Creditor
    debtor_account_number: str = Field(alias="debtorAccountNumber")
    currency_amount: CurrencyAmount = Field(alias="currencyAmount")
    execution_date: date = Field(alias="executionDate")


class PaymentsResponse(_Model):
    payments: list[Payment]
