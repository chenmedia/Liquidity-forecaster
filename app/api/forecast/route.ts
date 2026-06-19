import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { isAllowedEmail } from "@/lib/access";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Authenticated proxy: Clerk gates the user + email domain, then we call the
// internal Python compute function (gated by INTERNAL_API_SECRET). The browser
// never talks to the Python function directly.
export async function GET(req: Request) {
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

  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "dashboard not configured" }, { status: 503 });
  }

  const origin = new URL(req.url).origin;
  let res: Response;
  try {
    res = await fetch(`${origin}/api/compute`, {
      headers: { "X-Internal-Secret": secret },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "forecast unavailable" }, { status: 502 });
  }
  if (!res.ok) {
    return NextResponse.json({ error: "forecast unavailable" }, { status: 502 });
  }

  const data = await res.json();
  return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
}
