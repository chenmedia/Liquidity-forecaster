import { neon } from "@neondatabase/serverless";

// Neon / Vercel-Postgres integrations expose the connection string under varying
// names; accept the common ones so no manual DATABASE_URL wiring is needed.
function dbUrl(): string | undefined {
  return (
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL ||
    process.env.DATABASE_URL_UNPOOLED ||
    process.env.POSTGRES_URL_NON_POOLING
  );
}

// Reads the latest forecast snapshot published by the scheduled job (see
// src/liquidity_forecaster/publish.py). Returns null if no DB is configured or
// no snapshot exists yet.
export async function getLatestForecast(): Promise<unknown | null> {
  const url = dbUrl();
  if (!url) return null;
  const sql = neon(url);
  const rows = (await sql`
    SELECT payload FROM forecast_snapshot ORDER BY created_at DESC LIMIT 1
  `) as { payload: unknown }[];
  return rows[0]?.payload ?? null;
}
