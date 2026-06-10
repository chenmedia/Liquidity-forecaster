"""Command-line interface.

Subcommands:
  accounts       Fetch and print current balances by bucket (read-only sanity check).
  sync-history   Incrementally backfill cached daily balances.
  run            Project operational cash, evaluate the floor, and (optionally) alert.
"""

from __future__ import annotations

import argparse
import sys

from . import logging_setup
from .config import Config
from .folio_client import FolioAuthError
from .money import format_nok
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liquidity-forecaster", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("accounts", help="print current balances by bucket")
    sub.add_parser("sync-history", help="backfill cached daily balances")

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
        if args.command == "run":
            return _cmd_run(config, include_drafts=args.scenario == "drafts", dry_run=args.dry_run)
    except FolioAuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
