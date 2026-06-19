import { SignOutButton } from "@clerk/nextjs";
import { ALLOWED_EMAIL_DOMAIN } from "@/lib/access";

export default function Page() {
  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100vh", textAlign: "center" }}>
      <div>
        <h1>Access denied</h1>
        <p className="muted">
          The Liquidity Forecaster is restricted to <strong>@{ALLOWED_EMAIL_DOMAIN}</strong> accounts.
        </p>
        <p>
          <SignOutButton>
            <button>Sign out</button>
          </SignOutButton>
        </p>
      </div>
    </main>
  );
}
