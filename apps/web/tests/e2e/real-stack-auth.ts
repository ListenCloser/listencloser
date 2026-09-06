import { createHmac } from "node:crypto";
import { expect, type Page } from "@playwright/test";

/**
 * Shared auth session for real-stack E2E tests.
 *
 * All tests share a single Supabase user session via module-level state.
 * Safe because workers: 1 and fullyParallel: false guarantee serial execution.
 *
 * The production product exposes Google OAuth only. The real-stack test creates
 * its disposable user through the local admin API and mints a local JWT with the
 * CLI-provided JWT secret, so test setup does not depend on a user-facing email
 * or password provider being enabled.
 */

const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const JWT_SECRET = process.env.SUPABASE_JWT_SECRET;

function storageKey(url: string): string {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

function localAccessToken(user: Record<string, unknown>, email: string): string {
  if (!SUPABASE_URL || !JWT_SECRET || typeof user.id !== "string") {
    throw new Error("SUPABASE_URL / SUPABASE_JWT_SECRET and a test user id are required");
  }
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({
      aud: typeof user.aud === "string" ? user.aud : "authenticated",
      exp: now + 3600,
      iat: now,
      iss: `${SUPABASE_URL}/auth/v1`,
      sub: user.id,
      email,
      role: "authenticated",
      aal: "aal1",
      app_metadata: user.app_metadata ?? {},
      user_metadata: user.user_metadata ?? {},
    }),
  ).toString("base64url");
  const unsigned = `${header}.${payload}`;
  const signature = createHmac("sha256", JWT_SECRET).update(unsigned).digest("base64url");
  return `${unsigned}.${signature}`;
}

let session: Record<string, unknown> | null = null;

export async function getOrCreateSession(): Promise<Record<string, unknown>> {
  if (session) return session;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY || !JWT_SECRET) {
    throw new Error(
      "SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_JWT_SECRET must be set",
    );
  }
  const email = `e2e-${Date.now()}@real-stack.test`;

  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      email_confirm: true,
      app_metadata: { provider: "google", providers: ["google"] },
    }),
  });
  const createdBody = (await created.json().catch(() => ({}))) as Record<string, unknown>;
  if (!created.ok || typeof createdBody.id !== "string") {
    throw new Error(`failed to create test user: ${created.status} ${JSON.stringify(createdBody)}`);
  }

  const now = Math.floor(Date.now() / 1000);
  session = {
    access_token: localAccessToken(createdBody, email),
    token_type: "bearer",
    expires_in: 3600,
    expires_at: now + 3600,
    refresh_token: "",
    user: createdBody,
  };
  return session;
}

export async function injectAuth(page: Page) {
  const auth = await getOrCreateSession();
  await page.addInitScript(
    ({ key, session }) => {
      window.localStorage.setItem(key, JSON.stringify(session));
    },
    { key: storageKey(SUPABASE_URL!), session: auth },
  );
}

/**
 * Dismiss the "saved analysis could not be loaded" workspace notice if it
 * appears. Processing/recovery notices intentionally share the workspace-notice
 * container but are not dismissible, so probe the dismiss control itself.
 */
export async function dismissWorkspaceNotice(page: Page) {
  const dismiss = page.getByRole("button", { name: "Dismiss notice" });
  if (await dismiss.isVisible({ timeout: 2_000 }).catch(() => false)) {
    const notice = dismiss.locator(
      "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' workspace-notice ')][1]",
    );
    await dismiss.click();
    await expect(notice).toBeHidden({ timeout: 5_000 });
  }
}
