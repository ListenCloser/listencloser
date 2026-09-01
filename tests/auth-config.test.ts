import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const authConfig = readFileSync(
  resolve(process.cwd(), "supabase/config.toml"),
  "utf8",
);

function booleanSetting(section: string, key: string): boolean {
  let activeSection: string | null = null;

  for (const rawLine of authConfig.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }

    const sectionMatch = line.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      activeSection = sectionMatch[1];
      continue;
    }

    if (activeSection !== section) {
      continue;
    }

    const settingMatch = line.match(/^([A-Za-z0-9_]+)\s*=\s*(true|false)$/);
    if (settingMatch?.[1] === key) {
      return settingMatch[2] === "true";
    }
  }

  throw new Error(`Missing boolean setting ${section}.${key}`);
}

describe("Supabase auth configuration", () => {
  it("allows OAuth account creation while blocking unsupported direct signups", () => {
    // Global signup must stay enabled so first-time OAuth users can be created.
    expect(booleanSetting("auth", "enable_signup")).toBe(true);

    // Product auth is OAuth-only; direct email/SMS account creation must stay disabled.
    expect(booleanSetting("auth.email", "enable_signup")).toBe(false);
    expect(booleanSetting("auth.sms", "enable_signup")).toBe(false);
    expect(booleanSetting("auth", "enable_anonymous_sign_ins")).toBe(false);
  });
});
