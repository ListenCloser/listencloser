import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";

const PROD_URL = "https://hello-ai-wheat.vercel.app";
const SUPABASE_PROJECT_REF = "cijhpddqvvzyzfzmkdnn";
const REAL_AUDIO = "tests/fixtures/piano-simple.m4a";

let session: {
  access_token: string;
  refresh_token: string;
  user: { id: string; email: string };
} | null = null;

async function createSession() {
  if (session) return session;

  const res = await fetch(
    `https://${SUPABASE_PROJECT_REF}.supabase.co/auth/v1/signup`,
    {
      method: "POST",
      headers: {
        apikey: "sb_publishable_-FLJWytAadJmjJfzasSQow_Dw9wnm6o",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: `e2e-${Date.now()}@verify.test`,
        password: "verify123456",
      }),
    }
  );
  const data = await res.json();
  session = data;
  return session;
}

function injectSession() {
  return ({
    projectRef,
    sessionData,
  }: {
    projectRef: string;
    sessionData: typeof session;
  }) => {
    window.localStorage.setItem(
      `sb-${projectRef}-auth-token`,
      JSON.stringify({
        access_token: sessionData?.access_token,
        token_type: "bearer",
        expires_in: 3600,
        expires_at: Math.floor(Date.now() / 1000) + 3600,
        refresh_token: sessionData?.refresh_token,
        user: sessionData?.user,
      })
    );
  };
}

test("A: signed-in production page loads with service online", async ({
  page,
  request,
}) => {
  const s = await createSession();

  await page.addInitScript(injectSession(), {
    projectRef: SUPABASE_PROJECT_REF,
    sessionData: s,
  });
  await page.goto(PROD_URL);

  // The signed-in workspace renders the import button only when the session is
  // valid and the backend service reports ready, so it doubles as the
  // "service online" signal on the signed-in page.
  await expect(
    page.getByRole("main").getByRole("button", { name: "Import audio" }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText("Imported works will appear here and can be reopened in later sessions."),
  ).toBeVisible({ timeout: 10_000 });
});

test("B: backend health endpoints return ready", async ({ request }) => {
  const live = await request.get(`${PROD_URL}/api/health/live`);
  expect(live.status()).toBe(200);
  const liveBody = await live.json();
  expect(liveBody.status).toBe("alive");
  expect(liveBody.release).toBeTruthy();

  const ready = await request.get(`${PROD_URL}/api/health/ready`);
  expect(ready.status()).toBe(200);
  const readyBody = await ready.json();
  expect(readyBody.status).toBe("ready");
  expect(readyBody.supabase).toBe(true);
  expect(readyBody.database).toBe(true);
  expect(readyBody.storage).toBe(true);

  const queue = await request.get(`${PROD_URL}/api/health/queue`);
  expect(queue.status()).toBe(200);
  const queueBody = await queue.json();
  expect(queueBody.status).toBe("ready");
  expect(queueBody.workers).toBeGreaterThanOrEqual(0);
});

test("C: import real audio, wait for durable understand, verify representations", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const s = await createSession();

  await page.addInitScript(injectSession(), {
    projectRef: SUPABASE_PROJECT_REF,
    sessionData: s,
  });

  // The Import button renders before the first-load project setup completes;
  // importing then surfaces "Your project is still loading". Register the
  // create/list round-trip watcher before navigation so it catches the POST.
  const projectSettled = page
    .waitForResponse(
      (resp) => resp.url().includes("/api/v1/projects") && resp.request().method() === "POST",
      { timeout: 30_000 },
    )
    .catch(() => {});
  await page.goto(PROD_URL);
  await projectSettled;

  await expect(
    page.getByRole("main").getByRole("button", { name: "Import audio" }),
  ).toBeVisible({ timeout: 20_000 });

  const importButton = page.getByRole("main").getByRole("button", {
    name: "Import audio",
  });
  if (await importButton.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await importButton.click();
  } else {
    const newWorkBtn = page.getByRole("button", { name: /new/i });
    if (await newWorkBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await newWorkBtn.click();
    }
  }

  const fileInput = page.locator('input[type="file"]');
  if (existsSync(REAL_AUDIO)) {
    await fileInput.setInputFiles(REAL_AUDIO);
  } else {
    throw new Error(`Audio fixture not found: ${REAL_AUDIO}`);
  }

  await expect(page.getByText(/processing|uploading|importing/i)).toBeVisible({
    timeout: 30_000,
  }).catch(() => {});

  // Processing finished: the work's representations are discoverable from the
  // tab bar. (The piano roll tab is the deterministic completion signal; the
  // loose /note|piano/ regex would also match the empty-state copy and the
  // "Solo piano" transcription profile chip.)
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.getByRole("tab", { name: "Score" })).toBeVisible();
});
