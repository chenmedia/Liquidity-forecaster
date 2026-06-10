"""Render an alert payload, shared by Slack and the email fallback."""

from __future__ import annotations

from ..forecast import Forecast, Severity
from ..money import format_nok

_EMOJI = {Severity.GREEN: "🟢", Severity.AMBER: "🟡", Severity.RED: "🔴"}


def _lead_summary(f: Forecast) -> str:
    if f.severity is Severity.GREEN:
        return (
            f"Operational cash stays above the warning band through "
            f"{f.end_date.isoformat()} (low point {format_nok(f.trough_balance)} on "
            f"{f.trough_date.isoformat()})."
        )
    where = "below floor" if f.severity is Severity.RED else "into the warning band"
    breach = f.first_breach_date or f.trough_date
    lead_days = (breach - f.start_date).days
    return (
        f"Operational cash is projected {where}: low point "
        f"{format_nok(f.trough_balance)} on {f.trough_date.isoformat()} "
        f"(floor {format_nok(f.floor)}, shortfall {format_nok(f.shortfall)}); "
        f"first crossing {breach.isoformat()} — {lead_days} days out."
    )


def _drivers_lines(f: Forecast) -> list[str]:
    return [
        f"• {i.execution_date.isoformat()} · {i.creditor} · {format_nok(i.amount)}"
        for i in f.drivers
    ]


def render_subject(f: Forecast) -> str:
    if f.severity is Severity.GREEN:
        return "[GREEN] Operational cash above floor"
    state = "below floor" if f.severity is Severity.RED else "in warning band"
    when = (f.first_breach_date or f.trough_date).isoformat()
    return (
        f"[{f.severity.name}] Operational cash {state} on {when} — "
        f"shortfall {format_nok(f.shortfall)}"
    )


def render_text(f: Forecast) -> str:
    lines = [f"{_EMOJI[f.severity]} {f.severity.name} — Liquidity Forecast", "", _lead_summary(f)]
    drivers = _drivers_lines(f)
    if drivers:
        lines += ["", "Drivers:", *drivers]
    if f.severity is not Severity.GREEN:
        clears = "yes" if f.draw_on_savings_clears else "no"
        lines += [
            "",
            f"Draw on Savings clears it? {clears} (Savings {format_nok(f.savings_balance)})",
        ]
    if f.has_retrying:
        lines += ["", "⚠️ A payment is retrying for insufficient funds — funds are short now."]
    if f.low_confidence:
        lines += ["", "Note: forecast confidence is low (pending/unsettled transactions)."]
    return "\n".join(lines)


def render_blocks(f: Forecast) -> list[dict[str, object]]:
    """Slack Block Kit blocks."""
    blocks: list[dict[str, object]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{_EMOJI[f.severity]} {f.severity.name} — Liquidity Forecast",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": _lead_summary(f)}},
    ]
    drivers = _drivers_lines(f)
    if drivers:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Drivers*\n" + "\n".join(drivers)},
            }
        )
    if f.severity is not Severity.GREEN:
        clears = "yes" if f.draw_on_savings_clears else "no"
        savings = format_nok(f.savings_balance)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Draw on Savings clears it? *{clears}* ({savings})",
                    }
                ],
            }
        )
    footer = "Forecast horizon to " + f.end_date.isoformat()
    if f.low_confidence:
        footer += " · ⚠️ low confidence (unsettled transactions)"
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})
    return blocks
