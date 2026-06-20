import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Public routes: sign-in / sign-up (and Clerk's sub-routes). Everything else
// requires an authenticated session.
const isPublic = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/access-denied",
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublic(req)) {
    await auth.protect();
  }
});

export const config = {
  // Run on everything except static assets and Next internals.
  matcher: ["/((?!_next|.*\\..*).*)", "/api/(.*)"],
};
