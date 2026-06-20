import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { isAllowedEmail } from "@/lib/access";
import { getLatestForecast } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Clerk gates the user + @chenmedia.no email; then we return the latest forecast
// snapshot from Neon (published by the scheduled job). No compute happens here.
export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const user = await currentUser();
  const email =
    user?.primaryEmailAddress?.emailAddress ?? user?.emailAddresses?.[0]?.emailAddress;
  if (!isAllowedEmail(email)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  let payload: unknown | null;
  try {
    payload = await getLatestForecast();
  } catch {
    return NextResponse.json({ error: "forecast store unavailable" }, { status: 502 });
  }
  if (payload == null) {
    return NextResponse.json({ error: "no forecast published yet" }, { status: 404 });
  }

  return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
}
