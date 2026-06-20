"""Orchestration: fetch → project → evaluate → notify.

Pure-ish glue so the steps stay individually testable. Network access is confined
to :class:`FolioClient` and the notify modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from .alerting import SendDecision, decide_send
from .baseline import compute_baseline
from .config import Config
from .folio_client import FolioClient
from .forecast import Forecast, _select_operational, build_forecast
from .inflows import load_expected_inflows
from .models import Account
from .notify import email_fallback, slack
from .notify.message import render_text
from .publish import publish_snapshot
from .serialize import forecast_to_dict
from .store import Store

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    forecast: Forecast
    decision: SendDecision
    delivered_via: str | None


def fetch_accounts(config: Config) -> list[Account]:
    with FolioClient(config) as client:
        return client.get_accounts().accounts


def sync_history(config: Config, *, today: date | None = None) -> int:
    """Incrementally backfill cached daily balances. Returns number fetched."""
    today = today or date.today()
    store = Store(config.db_path)
    fetched = 0
    try:
        with FolioClient(config) as client:
            accounts = client.get_accounts().accounts
            for account in accounts:
                for offset in range(1, config.lookback_days + 1):
                    day = today - timedelta(days=offset)
                    if store.has_balance(account.account_number, day):
                        continue
                    bal = client.get_balance(account.account_number, day)
                    store.put_balance(
                        account.account_number, day, bal.incoming_balance, bal.outgoing_balance
                    )
                    fetched += 1
    finally:
        store.close()
    return fetched


def compute_forecast(
    config: Config,
    store: Store,
    *,
    today: date | None = None,
    include_drafts: bool = False,
) -> Forecast:
    """Fetch live data and build the forecast (no alerting). Reused by the dashboard."""
    today = today or date.today()
    with FolioClient(config) as client:
        accounts = client.get_accounts().accounts
        end = today + timedelta(days=config.horizon_days)
        payments = client.get_payments(today, end).payments

    expected_inflows = load_expected_inflows(config.expected_inflows_file)

    baseline = None
    if config.enable_baseline:
        op = _select_operational(accounts, config.operational_account)
        since = today - timedelta(days=config.lookback_days)
        nets = store.daily_nets(op.account_number, since)
        baseline = compute_baseline(nets, k=config.baseline_mad_k) or None
        if baseline is None:
            log.info("baseline skipped: insufficient history (run sync-history to populate)")

    return build_forecast(
        accounts,
        payments,
        config,
        today=today,
        include_drafts=include_drafts,
        baseline=baseline,
        expected_inflows=expected_inflows,
    )


def run(
    config: Config,
    *,
    today: date | None = None,
    include_drafts: bool = False,
    dry_run: bool = False,
) -> RunResult:
    """Full forecast + alert run."""
    today = today or date.today()
    store = Store(config.db_path)
    try:
        forecast = compute_forecast(config, store, today=today, include_drafts=include_drafts)

        decision = decide_send(forecast, store.last_alert(), config)
        delivered_via: str | None = None
        if decision.should_send:
            delivered_via = _deliver(forecast, config, dry_run=dry_run)
            store.record_alert(forecast, created_at=today.isoformat(), delivered_via=delivered_via)
        else:
            log.info("not sending: %s", decision.reason)
    finally:
        store.close()

    # Publish the snapshot for the dashboard (best-effort; never breaks the run).
    try:
        publish_snapshot(forecast_to_dict(forecast))
    except Exception:  # noqa: BLE001
        log.exception("failed to publish dashboard snapshot")

    return RunResult(forecast=forecast, decision=decision, delivered_via=delivered_via)


def publish_only(
    config: Config, *, today: date | None = None, include_drafts: bool = False
) -> bool:
    """Compute the forecast and publish the dashboard snapshot, without alerting."""
    store = Store(config.db_path)
    try:
        forecast = compute_forecast(config, store, today=today, include_drafts=include_drafts)
    finally:
        store.close()
    return publish_snapshot(forecast_to_dict(forecast))


def _deliver(forecast: Forecast, config: Config, *, dry_run: bool) -> str:
    """Deliver via Slack, falling back to email. Returns the channel used."""
    if dry_run:
        print(render_text(forecast))
        return "dry-run"
    try:
        slack.send_slack(forecast, channel=config.slack_channel)
        return "slack"
    except (slack.SlackNotConfigured, slack.SlackDeliveryError) as exc:
        log.warning("Slack delivery unavailable (%s); trying email fallback", type(exc).__name__)
        try:
            email_fallback.send_email(forecast, to_addr=config.alert_email_to)
            return "email"
        except email_fallback.EmailNotConfigured:
            log.error("No delivery channel configured; alert not sent")
            return "none"
