"""Internal Vercel Python function: returns the forecast as JSON.

GET /api/compute — **internal only**. Requires the ``X-Internal-Secret`` header to
match ``INTERNAL_API_SECRET``. The Next.js route handler (which does the Clerk user
auth + @chenmedia.no allowlist) is the only intended caller; the browser never hits
this directly. Fails closed if the secret isn't configured.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler

# The package lives under src/; bundled into the function via vercel.json includeFiles.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from liquidity_forecaster import web  # noqa: E402

log = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        try:
            web.check_internal_secret(self.headers.get("X-Internal-Secret"))
        except web.NotConfigured:
            return self._json(503, {"error": "compute not configured"})
        except web.InternalAuthError:
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
