import { defineConfig } from "@playwright/test";

/**
 * Real-stack browser E2E: runs the built app against a real backend + worker +
 * local Supabase. The stack is orchestrated by the `real-stack-e2e` CI job, so
 * no `webServer` is started here — the job owns the server lifecycle.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "real-stack-workflow.spec.ts",
  timeout: 600_000,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [["dot"]] : [["list"]],
  use: {
    baseURL: process.env.REAL_STACK_APP_URL || "http://localhost:3000",
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
});
