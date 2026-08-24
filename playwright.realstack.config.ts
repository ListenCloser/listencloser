import { defineConfig } from "@playwright/test";
import path from "node:path";

/**
 * Real-stack browser E2E: runs the built app against a real backend + worker +
 * local Supabase. The stack is orchestrated by the `real-stack-e2e` CI job, so
 * no `webServer` is started here — the job owns the server lifecycle.
 *
 * Architecture:
 *   1. "setup" project creates a user, imports audio, waits for processing,
 *      and saves browser storageState (localStorage with Supabase session).
 *   2. Test projects depend on "setup" and inherit the storageState, so each
 *      test gets an authenticated browser context with the processed work
 *      already available.
 *   3. Each test has an isolated browser context — no shared in-memory state.
 *   4. One expensive audio import per CI run.
 */

const STORAGE_STATE_PATH = path.join(
  process.env.PLAYWRIGHT_STORAGE_DIR ?? "/tmp",
  "real-stack-storage-state.json",
);

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 300_000,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [["dot"]] : [["list"]],
  projects: [
    {
      name: "setup",
      testMatch: /real-stack-setup\.spec\.ts/,
      use: {
        baseURL: process.env.REAL_STACK_APP_URL || "http://localhost:3000",
        viewport: { width: 1280, height: 900 },
        trace: "retain-on-failure",
        launchOptions: {
          args: ["--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        },
      },
    },
    {
      name: "workflow",
      testMatch: /real-stack-workflow\.spec\.ts/,
      dependencies: ["setup"],
      use: {
        baseURL: process.env.REAL_STACK_APP_URL || "http://localhost:3000",
        viewport: { width: 1280, height: 900 },
        storageState: STORAGE_STATE_PATH,
        trace: "retain-on-failure",
        launchOptions: {
          args: ["--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        },
      },
    },
    {
      name: "inspector",
      testMatch: /real-stack-inspector\.spec\.ts/,
      dependencies: ["setup"],
      use: {
        baseURL: process.env.REAL_STACK_APP_URL || "http://localhost:3000",
        viewport: { width: 1440, height: 900 },
        storageState: STORAGE_STATE_PATH,
        trace: "retain-on-failure",
        launchOptions: {
          args: ["--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        },
      },
    },
    {
      name: "ask",
      testMatch: /real-stack-ask\.spec\.ts/,
      dependencies: ["setup"],
      use: {
        baseURL: process.env.REAL_STACK_APP_URL || "http://localhost:3000",
        viewport: { width: 1440, height: 900 },
        storageState: STORAGE_STATE_PATH,
        trace: "retain-on-failure",
        launchOptions: {
          args: ["--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        },
      },
    },
  ],
});
