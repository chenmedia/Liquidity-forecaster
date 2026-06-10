"""Logging with secret/PII redaction.

Per docs/06-security.md §6: never log tokens, webhook URLs, or unmasked account
numbers. This installs a logging filter that masks them defensively even if a
caller accidentally includes one in a message.
"""

from __future__ import annotations

import logging
import re

# Bearer tokens / Folio keys (fk.<...>) and Slack webhook URLs.
_TOKEN_RE = re.compile(r"\b(fk\.[A-Za-z0-9_-]{6,}|xox[baprs]-[A-Za-z0-9-]{6,})\b")
_WEBHOOK_RE = re.compile(r"https://hooks\.slack\.com/services/\S+")
_ACCOUNT_RE = re.compile(r"\b(\d{6,})(\d{4})\b")


def _redact(text: str) -> str:
    text = _TOKEN_RE.sub("***REDACTED-TOKEN***", text)
    text = _WEBHOOK_RE.sub("https://hooks.slack.com/services/***REDACTED***", text)
    # Mask all but the last 4 digits of long account-number-like runs.
    text = _ACCOUNT_RE.sub(lambda m: "*" * len(m.group(1)) + m.group(2), text)
    return text


class RedactionFilter(logging.Filter):
    """Redact secrets and account numbers from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            record.args = tuple(_redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def configure(level: int = logging.INFO) -> None:
    """Configure root logging with the redaction filter attached."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
