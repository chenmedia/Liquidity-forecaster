"""Publish the latest forecast snapshot to Postgres (Neon) for the dashboard.

The scheduled run computes the forecast and writes it here; the Next.js dashboard
reads the most recent row. This keeps the dashboard on a single runtime (no Python
on Vercel) and gives real persistence. Publishing is best-effort — a failure must
never break alerting.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# Neon / Vercel-Postgres integrations expose the connection string under varying
# names; accept the common ones so no manual DATABASE_URL wiring is needed.
_URL_ENV_VARS = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "DATABASE_URL_UNPOOLED",
    "POSTGRES_URL_NON_POOLING",
)


def _resolve_url() -> str | None:
    return next((os.environ[v] for v in _URL_ENV_VARS if os.environ.get(v)), None)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast_snapshot (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
)
"""

_INSERT = "INSERT INTO forecast_snapshot (payload) VALUES (%s)"

_PRUNE = (
    "DELETE FROM forecast_snapshot WHERE id NOT IN "
    "(SELECT id FROM forecast_snapshot ORDER BY created_at DESC LIMIT %s)"
)


def publish_snapshot(
    payload: dict[str, object], *, database_url: str | None = None, keep: int = 30
) -> bool:
    """Write a forecast snapshot to Postgres. Returns False if unconfigured."""
    url = database_url or _resolve_url()
    if not url:
        log.info("no database URL set; skipping dashboard snapshot publish")
        return False

    # Imported lazily so the package doesn't hard-require psycopg unless publishing.
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
            cur.execute(_INSERT, (Jsonb(payload),))
            cur.execute(_PRUNE, (keep,))
        conn.commit()
    log.info("published forecast snapshot to dashboard store")
    return True
