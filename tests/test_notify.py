"""Message rendering, redaction, and the Slack→email fallback path."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from liquidity_forecaster.config import Config
from liquidity_forecaster.forecast import build_forecast
from liquidity_forecaster.logging_setup import RedactionFilter
from liquidity_forecaster.models import AccountsResponse, PaymentsResponse
from liquidity_forecaster.notify import slack
from liquidity_forecaster.notify.message import render_blocks, render_subject, render_text

from . import fixtures


def _forecast():
    accounts = AccountsResponse.model_validate(fixtures.accounts_response()).accounts
    payments = PaymentsResponse.model_validate(fixtures.payments_response()).payments
    return build_forecast(accounts, payments, Config(), today=fixtures.TODAY)


def test_text_and_subject_contain_key_facts() -> None:
    f = _forecast()
    text = render_text(f)
    assert "RED" in text
    assert "160 000 NOK" in text  # shortfall
    assert "Sound & Light AS" in text and "Payroll" in text  # drivers
    assert "RED" in render_subject(f)
    assert isinstance(render_blocks(f), list)


def test_slack_not_configured_raises(monkeypatch) -> None:
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(slack.SlackNotConfigured):
        slack.send_slack(_forecast(), channel="#finance")


@respx.mock
def test_slack_success(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/secret")
    route = respx.post("https://hooks.slack.com/services/T/B/secret").mock(
        return_value=httpx.Response(200, text="ok")
    )
    with httpx.Client() as client:
        slack.send_slack(_forecast(), channel="#finance", client=client)
    assert route.called


def test_redaction_filter_masks_token_and_account() -> None:
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="key fk.SECRETTOKEN123456 acct 36060000001",
        args=(),
        exc_info=None,
    )
    RedactionFilter().filter(record)
    assert "fk.SECRETTOKEN123456" not in record.msg
    assert "36060000001" not in record.msg  # masked to last 4
    assert record.msg.endswith("0001")
