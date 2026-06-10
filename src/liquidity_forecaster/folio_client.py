"""Read-only Folio API client.

Security posture (docs/06-security.md §3): this client exposes **only GET**
methods for the endpoints the forecaster needs. There is deliberately no method
that creates, deletes, or modifies payments/events — the read-only guarantee is
structural, not just policy.

The API key is read from ``FOLIO_API_KEY`` at construction and never logged.
"""

from __future__ import annotations

import os
import time
from datetime import date

import httpx

from .config import Config
from .models import AccountBalance, AccountsResponse, PaymentsResponse

_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_RETRY_STATUS = {429, 500, 502, 503, 504}


class FolioAuthError(RuntimeError):
    """Raised when no API key is configured."""


class FolioClient:
    """Minimal read-only client for the Folio v2 API."""

    def __init__(self, config: Config | None = None, *, client: httpx.Client | None = None) -> None:
        self._config = config or Config()
        api_key = os.environ.get("FOLIO_API_KEY")
        if not api_key:
            raise FolioAuthError(
                "FOLIO_API_KEY is not set. Provide it via the environment / a secret "
                "store (see docs/SECRETS.md); never hard-code or commit it."
            )
        # TLS verification is on by default in httpx; we do not disable it.
        self._client = client or httpx.Client(
            base_url=self._config.folio_base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_DEFAULT_TIMEOUT,
        )

    def __enter__(self) -> FolioClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # --- internal -------------------------------------------------------
    def _get(
        self, path: str, *, params: dict[str, str] | None = None, _attempt: int = 0
    ) -> httpx.Response:
        resp = self._client.get(path, params=params)
        if resp.status_code in _RETRY_STATUS and _attempt < 3:
            time.sleep(2**_attempt)
            return self._get(path, params=params, _attempt=_attempt + 1)
        resp.raise_for_status()
        return resp

    # --- read endpoints -------------------------------------------------
    def get_accounts(self) -> AccountsResponse:
        return AccountsResponse.model_validate(self._get("/accounts").json())

    def get_balance(self, account_number: str, on: date) -> AccountBalance:
        return AccountBalance.model_validate(
            self._get(f"/accounts/{account_number}/balance/{on.isoformat()}").json()
        )

    def get_payments(self, start: date, end: date) -> PaymentsResponse:
        """List payments between ``start`` and ``end`` (inclusive).

        ``end`` is always sent explicitly: the API defaults ``endDate`` to *today*,
        which would silently drop future-dated scheduled payments (AC-4).
        """
        if end < start:
            raise ValueError("end date must be on or after start date")
        params = {"startDate": start.isoformat(), "endDate": end.isoformat()}
        return PaymentsResponse.model_validate(self._get("/payments", params=params).json())
