import { defineConfig } from "@playwright/test";
import { createArgosReporterOptions } from "@argos-ci/playwright/reporter";

const runProductionVerify = process.env.RUN_PRODUCTION_VERIFY === "true";

export default defineConfig({
  testDir: "./tests",
  testIgnore: [
    "**/components/**",
    "**/lib/**",
    "**/domain-contract.test.ts",
    ...(runProductionVerify ? [] : ["**/production-verify.spec.ts"]),
  ],
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: (() => {
    const list: any[] = [process.env.CI ? ["dot"] : ["list"]];
    if (process.env.CI) {
      list.push(["./tests/visual/retain-screenshots-reporter.ts"]);
    }
    if (process.env.ARGOS_TOKEN) {
      list.push([
        "@argos-ci/playwright/reporter",
        createArgosReporterOptions({ uploadToArgos: true }),
      ]);
    }
    return list;
  })(),
  webServer: runProductionVerify
    ? undefined
    : {
        command: "npm run dev -- --hostname 127.0.0.1",
        url: process.env.BASE_URL || "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
        env: {
          ...process.env,
          NEXT_PUBLIC_MOCK_ENABLED: "true",
          NEXT_PUBLIC_SUPABASE_URL:
            process.env.NEXT_PUBLIC_SUPABASE_URL ||
            "https://cijhpddqvvzyzfzmkdnn.supabase.co",
          NEXT_PUBLIC_SUPABASE_ANON_KEY:
            process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "e2e-anon-key",
        },
      },
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    viewport: { width: 1180, height: 1000 },
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    launchOptions: {
      args: ["--disable-lcd-text", "--font-render-hinting=none"],
    },
  },
});