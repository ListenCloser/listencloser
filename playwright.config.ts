import { defineConfig } from "@playwright/test";
import { createArgosReporterOptions } from "@argos-ci/playwright/reporter";

export default defineConfig({
  testDir: "./tests",
  testIgnore: ["**/components/**", "**/domain-contract.test.ts"],
  timeout: 30_000,
  reporter: (() => {
    const list: any[] = [process.env.CI ? ["dot"] : ["list"]];
    if (process.env.ARGOS_TOKEN) {
      list.push([
        "@argos-ci/playwright/reporter",
        createArgosReporterOptions({ uploadToArgos: true }),
      ]);
    }
    return list;
  })(),
  webServer: {
    command: "npm run dev",
    url: process.env.BASE_URL || "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      ...process.env,
      NEXT_PUBLIC_MOCK_ENABLED: "true",
    },
  },
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    viewport: { width: 1180, height: 1000 },
    launchOptions: {
      args: ["--disable-lcd-text", "--font-render-hinting=none"],
    },
  },
});
