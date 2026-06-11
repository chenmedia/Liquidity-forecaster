"""Command-line interface.

Subcommands:
  accounts       Fetch and print current balances by bucket (read-only sanity check).
  sync-history   Incrementally backfill cached daily balances.
  send-test      Post a sample alert to verify the Slack channel.
  run            Project operational cash, evaluate the floor, and (optionally) alert.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal

from . import logging_setup
from .config import Config
from .folio_client import FolioAuthError
from .forecast import Forecast, Severity
from .money import format_nok
from .notify import slack
from .notify.message import render_text
from .pipeline import fetch_accounts, run, sync_history


def _cmd_accounts(config: Config) -> int:
    accounts = fetch_accounts(config)
    print("Accounts (balances are read-only):\n")
    for a in sorted(accounts, key=lambda x: x.type.value):
        print(f"  {a.type.value:<12} {a.name:<24} {format_nok(a.balance)}")
    print(f"\nFloor is {format_nok(config.operational_floor)} — adjust FORECAST_FLOOR if needed.")
    return 0


def _cmd_sync_history(config: Config) -> int:
    fetched = sync_history(config)
    print(f"Synced {fetched} new daily-balance record(s).")
    return 0


def _cmd_run(config: Config, *, include_drafts: bool, dry_run: bool) -> int:
    result = run(config, include_drafts=include_drafts, dry_run=dry_run)
    f = result.forecast
    print(render_text(f))
    print()
    if result.decision.should_send:
        print(f"Alert sent via: {result.delivered_via} ({result.decision.reason})")
    else:
        print(f"No alert sent ({result.decision.reason})")
    return 0


def _sample_forecast(config: Config) -> Forecast:
    """A benign GREEN forecast used to verify the alert channel end-to-end."""
    today = date.today()
    end = today + timedelta(days=config.horizon_days)
    balance = config.operational_floor + Decimal("100000")
    return Forecast(
        operational_account="TEST",
        start_date=today,
        end_date=end,
        start_balance=balance,
        savings_balance=Decimal("0"),
        floor=config.operational_floor,
        amber_threshold=config.amber_threshold(),
        curve=[(today, balance), (end, balance)],
        items=[],
        trough_date=today,
        trough_balance=balance,
        first_breach_date=None,
        severity=Severity.GREEN,
        has_retrying=False,
        low_confidence=False,
    )


def _cmd_send_test(config: Config) -> int:
    forecast = _sample_forecast(config)
    try:
        slack.send_slack(forecast, channel=config.slack_channel)
    except slack.SlackNotConfigured:
        print("error: SLACK_WEBHOOK_URL is not set (see docs/SECRETS.md)", file=sys.stderr)
        return 2
    except slack.SlackDeliveryError as exc:
        print(f"error: Slack delivery failed: {exc}", file=sys.stderr)
        return 2
    print(f"Test alert posted to Slack {config.slack_channel}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liquidity-forecaster", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("accounts", help="print current balances by bucket")
    sub.add_parser("sync-history", help="backfill cached daily balances")
    sub.add_parser("send-test", help="post a sample alert to verify the Slack channel")

    run_p = sub.add_parser("run", help="project cash and evaluate the floor")
    run_p.add_argument(
        "--scenario",
        choices=["committed", "drafts"],
        default="committed",
        help="committed (default) counts InProcess; drafts also counts Draft payments",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the alert instead of sending to Slack/email",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging_setup.configure()
    args = build_parser().parse_args(argv)
    config = Config()
    try:
        if args.command == "accounts":
            return _cmd_accounts(config)
        if args.command == "sync-history":
            return _cmd_sync_history(config)
        if args.command == "send-test":
            return _cmd_send_test(config)
        if args.command == "run":
            return _cmd_run(config, include_drafts=args.scenario == "drafts", dry_run=args.dry_run)
    except FolioAuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
