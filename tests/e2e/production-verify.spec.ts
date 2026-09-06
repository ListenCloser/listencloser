import { expect, test } from "@playwright/test";
import { createClient } from "@supabase/supabase-js";
import { existsSync, readFileSync } from "node:fs";

const PROD_URL = "https://listen-closer.vercel.app";
const SUPABASE_PROJECT_REF = "cijhpddqvvzyzfzmkdnn";
const SUPABASE_URL = `https://${SUPABASE_PROJECT_REF}.supabase.co`;
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_-FLJWytAadJmjJfzasSQow_Dw9wnm6o";
const REAL_AUDIO = "tests/fixtures/piano-simple.m4a";

type VerifierSession = {
  access_token: string;
  refresh_token: string;
  user: { id: string; email?: string };
};

let session: VerifierSession | null = null;

async function createSession(): Promise<VerifierSession> {
  if (session) return session;

  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceRoleKey) {
    throw new Error("SUPABASE_SERVICE_ROLE_KEY is required for Production Verify auth setup.");
  }

  // Product authentication is Google-only. Production verification needs an
  // authenticated hosted user without re-enabling a public email/password
  // provider, so create a one-time email link through the server-only Admin API
  // and exchange its token for an ordinary user session before the browser starts.
  const admin = createClient(SUPABASE_URL, serviceRoleKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
  const verifier = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
  const email = `e2e-prod-${Date.now()}-${crypto.randomUUID()}@verify.listencloser.test`;

  const { data: linkData, error: linkError } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  if (linkError || !linkData.properties?.hashed_token) {
    throw new Error(`Production Verify auth link setup failed: ${linkError?.message ?? "missing token"}`);
  }

  const { data: verified, error: verifyError } = await verifier.auth.verifyOtp({
    token_hash: linkData.properties.hashed_token,
    type: linkData.properties.verification_type,
  });
  if (verifyError || !verified.session) {
    throw new Error(`Production Verify auth exchange failed: ${verifyError?.message ?? "missing session"}`);
  }

  session = verified.session;
  return session;
}

function injectSession() {
  return ({
    projectRef,
    sessionData,
  }: {
    projectRef: string;
    sessionData: VerifierSession;
  }) => {
    window.localStorage.setItem(
      `sb-${projectRef}-auth-token`,
      JSON.stringify({
        access_token: sessionData.access_token,
        token_type: "bearer",
        expires_in: 3600,
        expires_at: Math.floor(Date.now() / 1000) + 3600,
        refresh_token: sessionData.refresh_token,
        user: sessionData.user,
      })
    );
  };
}

test("A: signed-in production page loads with service online", async ({
  page,
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
  await expect(page.getByRole("heading", { name: /^(Bring in a recording\.|Import a recording)$/ })).toBeVisible({ timeout: 10_000 });
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

  // Deploy-backend passes DEPLOY_SHA so verification proves the exact intended
  // revision is live. A stale Oracle backend (e.g. a silently skipped or failed
  // deployment) fails here instead of passing a frontend-only check.
  const expectedRelease = process.env.DEPLOY_SHA;
  if (expectedRelease) {
    expect(readyBody.release).toBe(expectedRelease);
  }
  expect(readyBody.release).toBeTruthy();

  const queue = await request.get(`${PROD_URL}/api/health/queue`);
  expect(queue.status()).toBe(200);
  const queueBody = await queue.json();
  expect(queueBody.status).toBe("ready");
  expect(queueBody.workers).toBeGreaterThanOrEqual(0);
});

test("C: import real audio, wait for durable understand, verify representations and Ask", async ({
  page,
}) => {
  test.setTimeout(220_000);
  const s = await createSession();

  await page.addInitScript(injectSession(), {
    projectRef: SUPABASE_PROJECT_REF,
    sessionData: s,
  });

  // Wait for durable library hydration, not merely project creation.
  const librarySettled = page
    .waitForResponse(
      (resp) => /\/api\/v1\/projects\/[^/]+\/works$/.test(new URL(resp.url()).pathname) && resp.request().method() === "GET",
      { timeout: 30_000 },
    )
    .catch(() => {});
  await page.goto(PROD_URL);
  await librarySettled;

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

  const fileInput = page.locator("#audio-import-input");
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

  // Cross the same browser → Vercel proxy → FastAPI → configured provider
  // boundary as a real user. Mocked E2E cannot detect a missing provider,
  // deployment drift, proxy timeout, or production-only reachability failure.
  await page.getByRole("tab", { name: "Ask" }).click();
  const askInput = page.getByRole("textbox", { name: "Ask about the music" });
  await expect(askInput).toBeVisible();
  await askInput.fill("What tonal center is supported by the available evidence?");

  const askResponsePromise = page.waitForResponse(
    (resp) => new URL(resp.url()).pathname === "/api/v1/ask" && resp.request().method() === "POST",
    { timeout: 60_000 },
  );
  await page.getByRole("button", { name: "Send question" }).click();
  const askResponse = await askResponsePromise;
  const requestId = askResponse.headers()["x-request-id"] ?? "missing";
  expect(
    askResponse.status(),
    `production Ask failed with status ${askResponse.status()} (request ${requestId})`,
  ).toBe(200);

  await expect(page.locator(".ask-turn-assistant")).toBeVisible({ timeout: 10_000 });
  // Next.js mounts an empty route-announcer with role=alert outside the app.
  // Assert the actual ListenCloser Ask error surface is absent rather than
  // banning all ARIA alerts or matching one specific error message.
  await expect(page.locator(".ask-error")).toHaveCount(0);
});

test("D: real Pitch Contour job is accepted, executed, and completes", async ({
  request,
}) => {
  test.setTimeout(240_000);
  if (!existsSync(REAL_AUDIO)) {
    throw new Error(`Audio fixture not found: ${REAL_AUDIO}`);
  }
  const s = await createSession();
  const authHeaders = { Authorization: `Bearer ${s.access_token}` };

  const projectResponse = await request.post(`${PROD_URL}/api/v1/projects`, {
    headers: authHeaders,
    data: {
      name: `pitch-contour-prod-verify-${Date.now()}`,
      description: "production verify pitch contour",
    },
  });
  expect(projectResponse.status()).toBe(200);
  const projectId = (await projectResponse.json()).id as string;
  expect(projectId).toBeTruthy();

  const uploadResponse = await request.post(
    `${PROD_URL}/api/v1/projects/${projectId}/artifacts/upload`,
    {
      headers: authHeaders,
      multipart: {
        file: {
          name: "piano-simple.m4a",
          mimeType: "audio/mp4",
          buffer: readFileSync(REAL_AUDIO),
        },
      },
    },
  );
  expect(uploadResponse.status()).toBe(200);
  const versionId = (await uploadResponse.json()).version?.id as string;
  expect(versionId).toBeTruthy();

  const createResponse = await request.post(`${PROD_URL}/api/v1/workflows/create`, {
    headers: authHeaders,
    data: {
      version_id: versionId,
      project_id: projectId,
      action: "pitch_contour",
      parameters: { pitch_engine: "pyin" },
    },
  });
  expect(
    createResponse.status(),
    `pitch_contour rejected by /api/v1/workflows/create: ${await createResponse.text()}`,
  ).toBe(200);
  const created = await createResponse.json();
  const jobId = created.job?.id as string;
  expect(created.job?.capability).toBe("pitch_contour");
  expect(jobId).toBeTruthy();

  let stage = "";
  let message = "";
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    const jobResponse = await request.get(`${PROD_URL}/api/v1/jobs/${jobId}`, {
      headers: authHeaders,
    });
    expect(jobResponse.status()).toBe(200);
    const job = await jobResponse.json();
    stage = job.stage as string;
    message = job.message as string;
    if (stage === "succeeded") break;
    expect(stage, `pitch_contour job ${jobId} entered ${stage}: ${message}`).not.toBe(
      "failed",
    );
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  expect(
    stage,
    `pitch_contour job ${jobId} did not complete within 180s; last stage=${stage} message=${message}`,
  ).toBe("succeeded");
});
