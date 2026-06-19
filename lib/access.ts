// Email-domain allowlist for the dashboard. Defense-in-depth on top of the
// Clerk Dashboard sign-up restriction; kept pure so it is unit-testable.

export const ALLOWED_EMAIL_DOMAIN =
  process.env.DASHBOARD_ALLOWED_EMAIL_DOMAIN ?? "chenmedia.no";

export function isAllowedEmail(
  email: string | null | undefined,
  domain: string = ALLOWED_EMAIL_DOMAIN,
): boolean {
  if (!email) return false;
  const at = email.lastIndexOf("@");
  if (at < 0) return false;
  return email.slice(at + 1).toLowerCase() === domain.toLowerCase();
}
