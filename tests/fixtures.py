"""The docs/03-forecast.md worked example as Folio API payloads.

"Today" = 2026-06-10, floor 250 000, warning band 25%.
"""

from __future__ import annotations

from datetime import date

TODAY = date(2026, 6, 10)

OPERATIONAL_ACCOUNT = "36060000001"
SAVINGS_ACCOUNT = "36060000004"


def accounts_response() -> dict:
    ts = "2026-06-10T08:00:00Z"
    return {
        "accounts": [
            {
                "accountNumber": OPERATIONAL_ACCOUNT,
                "balance": "480000.00",
                "balanceUpdatedAt": ts,
                "matchingTransactionsAt": ts,
                "completeTransactionsAt": ts,
                "name": "Drift",
                "type": "Operational",
            },
            {
                "accountNumber": "36060000002",
                "balance": "220000.00",
                "balanceUpdatedAt": ts,
                "matchingTransactionsAt": ts,
                "completeTransactionsAt": ts,
                "name": "Skatt",
                "type": "Tax",
            },
            {
                "accountNumber": "36060000003",
                "balance": "150000.00",
                "balanceUpdatedAt": ts,
                "matchingTransactionsAt": ts,
                "completeTransactionsAt": ts,
                "name": "Øremerket",
                "type": "Earmarks",
            },
            {
                "accountNumber": SAVINGS_ACCOUNT,
                "balance": "300000.00",
                "balanceUpdatedAt": ts,
                "matchingTransactionsAt": ts,
                "completeTransactionsAt": ts,
                "name": "Sparing",
                "type": "Savings",
            },
        ]
    }


def _payment(pid: str, exec_date: str, creditor: str, amount: str, state: str) -> dict:
    return {
        "id": pid,
        "eventId": pid,
        "createdAt": "2026-06-01T08:00:00Z",
        "createdByAgentId": "00000000-0000-0000-0000-000000000000",
        "state": state,
        "creditor": {"name": creditor, "accountNumber": "9999999999"},
        "debtorAccountNumber": OPERATIONAL_ACCOUNT,
        "currencyAmount": {"amount": amount, "currency": "NOK"},
        "executionDate": exec_date,
    }


def payments_response() -> dict:
    return {
        "payments": [
            _payment("p1", "2026-06-15", "Sound & Light AS", "180000.00", "InProcess"),
            _payment("p2", "2026-06-25", "Payroll", "210000.00", "InProcess"),
            _payment("p3", "2026-06-25", "Tax (employer)", "95000.00", "Draft"),
            _payment("p4", "2026-07-10", "Venue deposit refund", "-120000.00", "InProcess"),
            _payment("p5", "2026-05-30", "Catering", "60000.00", "Completed"),
        ]
    }
