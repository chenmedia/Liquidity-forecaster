"""Email fallback — used only when Slack delivery fails (docs/04-alerting.md §4.5).

SMTP credentials are read from the environment at send time and never logged.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from ..forecast import Forecast
from .message import render_subject, render_text


class EmailNotConfigured(RuntimeError):
    pass


def send_email(forecast: Forecast, *, to_addr: str) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise EmailNotConfigured("SMTP_HOST is not set")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("ALERT_EMAIL_FROM", username or "forecaster@localhost")

    msg = EmailMessage()
    msg["Subject"] = render_subject(forecast)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(render_text(forecast))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls(context=context)
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
