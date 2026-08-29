import { expect, type Page } from "@playwright/test";

/**
 * Shared auth session for real-stack E2E tests.
 *
 * All tests share a single Supabase user session via module-level state.
 * Safe because workers: 1 and fullyParallel: false guarantee serial execution.
 */

const SUPABASE_URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function storageKey(url: string): string {
  return `sb-${new URL(url).hostname.split(".")[0]}-auth-token`;
}

let session: Record<string, unknown> | null = null;

export async function getOrCreateSession(): Promise<Record<string, unknown>> {
  if (session) return session;
  if (!SUPABASE_URL || !ANON_KEY || !SERVICE_KEY) {
    throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set");
  }
  const email = `e2e-${Date.now()}@real-stack.test`;
  const password = "real-stack-12345678";

  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  const createdBody = await created.json().catch(() => ({}));
  if (!created.ok && createdBody?.code !== "user_already_exists") {
    throw new Error(`failed to create test user: ${created.status} ${JSON.stringify(createdBody)}`);
  }

  const token = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const tokenBody = await token.json();
  if (!tokenBody?.access_token) {
    throw new Error(`failed to sign in test user: ${token.status} ${JSON.stringify(tokenBody)}`);
  }
  session = tokenBody;
  return tokenBody as Record<string, unknown>;
}

export async function injectAuth(page: Page) {
  const auth = await getOrCreateSession();
  await page.addInitScript(
    ({ key, session }) => {
      window.localStorage.setItem(
        key,
        JSON.stringify({
          access_token: session.access_token,
          token_type: "bearer",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: session.refresh_token ?? "",
          user: session.user,
        }),
      );
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
    const notice = dismiss.locator("xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' workspace-notice ')][1]");
    await dismiss.click();
    await expect(notice).toBeHidden({ timeout: 5_000 });
  }
}
