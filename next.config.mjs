// Security headers, including a Content-Security-Policy that allows Clerk.
// Clerk loads its script and talks to your Frontend API (dev: *.clerk.accounts.dev;
// production: clerk.<your-domain> — add that host here when you go to a prod instance).
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://*.clerk.accounts.dev https://challenges.cloudflare.com",
  "connect-src 'self' https://*.clerk.accounts.dev https://clerk-telemetry.com",
  "img-src 'self' https://img.clerk.com data:",
  "style-src 'self' 'unsafe-inline'",
  "frame-src 'self' https://*.clerk.accounts.dev https://challenges.cloudflare.com",
  "worker-src 'self' blob:",
  "form-action 'self'",
  "base-uri 'none'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
      {
        source: "/api/(.*)",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
};

export default nextConfig;
