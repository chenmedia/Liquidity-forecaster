"""Slack delivery via incoming webhook.

The webhook URL is read from ``SLACK_WEBHOOK_URL`` at send time and never logged.
Raises :class:`SlackDeliveryError` after exhausting retries so the caller can fall
back to email (docs/04-alerting.md §4.4).
"""

from __future__ import annotations

import os
import time

import httpx

from ..forecast import Forecast
from .message import render_blocks, render_text


class SlackNotConfigured(RuntimeError):
    pass


class SlackDeliveryError(RuntimeError):
    pass


def send_slack(forecast: Forecast, *, channel: str, client: httpx.Client | None = None) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        raise SlackNotConfigured("SLACK_WEBHOOK_URL is not set")

    payload = {
        "channel": channel,
        "text": render_text(forecast),  # fallback/notification text
        "blocks": render_blocks(forecast),
    }
    owns = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))
    try:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.post(webhook, json=payload)
                if resp.status_code == 200:
                    return
                last_exc = SlackDeliveryError(f"Slack returned HTTP {resp.status_code}")
            except httpx.HTTPError as exc:
                last_exc = exc
            time.sleep(2**attempt)
        raise SlackDeliveryError("Slack delivery failed after retries") from last_exc
    finally:
        if owns:
            client.close()
