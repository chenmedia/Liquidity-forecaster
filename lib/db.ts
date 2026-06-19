import { neon } from "@neondatabase/serverless";

// Reads the latest forecast snapshot published by the scheduled job (see
// src/liquidity_forecaster/publish.py). Returns null if no DB is configured or
// no snapshot exists yet.
export async function getLatestForecast(): Promise<unknown | null> {
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  const sql = neon(url);
  const rows = (await sql`
    SELECT payload FROM forecast_snapshot ORDER BY created_at DESC LIMIT 1
  `) as { payload: unknown }[];
  return rows[0]?.payload ?? null;
}
