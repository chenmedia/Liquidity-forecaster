"""Vercel Python serverless function: returns the current forecast as JSON.

GET /api/forecast — requires a ``DASHBOARD_TOKEN`` passed as the
``X-Dashboard-Token`` header or a ``?token=`` query param. Fails closed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# The package lives under src/; bundled into the function via vercel.json includeFiles.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from liquidity_forecaster import web  # noqa: E402

log = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (Vercel/BaseHTTPRequestHandler API)
        token = self.headers.get("X-Dashboard-Token") or _query_token(self.path)
        try:
            web.check_token(token)
        except web.NotConfigured:
            return self._json(503, {"error": "dashboard not configured"})
        except web.Unauthorized:
            return self._json(401, {"error": "unauthorized"})

        try:
            payload = web.build_payload()
        except Exception:  # noqa: BLE001 - never leak internals to the client
            log.exception("forecast computation failed")
            return self._json(502, {"error": "forecast unavailable"})

        self._json(200, payload)

    def _json(self, status: int, body: dict[str, object]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:  # silence default stderr logging
        pass


def _query_token(path: str) -> str | None:
    values = parse_qs(urlparse(path).query).get("token")
    return values[0] if values else None
