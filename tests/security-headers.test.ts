import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const nextConfig = readFileSync(join(process.cwd(), "next.config.mjs"), "utf8");

const expectedHeaders = [
  [
    "Content-Security-Policy",
    "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
  ],
  ["X-Frame-Options", "DENY"],
  ["X-Content-Type-Options", "nosniff"],
  ["Referrer-Policy", "strict-origin-when-cross-origin"],
] as const;

describe("browser security headers", () => {
  it("applies the baseline security headers to every route", () => {
    expect(nextConfig).toContain('source: "/:path*"');

    for (const [key, value] of expectedHeaders) {
      expect(nextConfig).toContain(`key: "${key}"`);
      expect(nextConfig).toContain(`value: "${value}"`);
    }
  });

  it("leaves HSTS ownership to the deployment platform", () => {
    expect(nextConfig).not.toContain("Strict-Transport-Security");
  });
});
