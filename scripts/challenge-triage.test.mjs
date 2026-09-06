import { afterEach, describe, expect, it } from "vitest";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { triageResults, writeTriage } from "./challenge-triage.mjs";

const tempDirs = [];

function fixtureDir() {
  const dir = mkdtempSync(join(tmpdir(), "listencloser-challenge-triage-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(() => {
  for (const dir of tempDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("challenge triage", () => {
  it("routes accessibility, mutation, and performance evidence without turning measurements into gates", () => {
    const dir = fixtureDir();
    writeFileSync(
      join(dir, "axe.json"),
      JSON.stringify({
        results: [
          {
            name: "workspace-desktop",
            violations: [
              {
                id: "color-contrast",
                impact: "serious",
                help: "Elements must meet minimum color contrast ratio thresholds",
                helpUrl: "https://example.test/contrast",
                nodes: [{ target: [".muted"] }, { target: ["#inactive-tab"] }],
              },
            ],
          },
        ],
      }),
    );
    writeFileSync(
      join(dir, "mutation-js.txt"),
      `[Survived] BooleanLiteral\nlib/evidence-projections.ts:277:15\n[NoCoverage] ObjectLiteral\nlib/evidence-projections.ts:307:10\nAll files | 73.58 | 82.98 | 39 | 0 | 8 | 6 | 0 |\n`,
    );
    mkdirSync(join(dir, "lighthouse"));
    writeFileSync(
      join(dir, "lighthouse", "lhr-1.json"),
      JSON.stringify({
        finalUrl: "http://127.0.0.1:3000/",
        categories: {
          performance: { score: 0.6 },
          accessibility: { score: 1 },
          "best-practices": { score: 1 },
          seo: { score: 1 },
        },
        audits: {
          "largest-contentful-paint": { numericValue: 5900 },
          "total-blocking-time": { numericValue: 730 },
          "cumulative-layout-shift": { numericValue: 0 },
          "unused-javascript": { details: { overallSavingsBytes: 304911 } },
        },
      }),
    );

    const first = triageResults(dir);
    const second = triageResults(dir);

    expect(first.findings).toHaveLength(3);
    expect(first.findings.map((finding) => finding.fingerprint)).toEqual(
      second.findings.map((finding) => finding.fingerprint),
    );

    const contrast = first.findings.find((finding) => finding.tool === "axe");
    expect(contrast).toMatchObject({
      ownerIssue: 1211,
      priority: "P1",
      disposition: "READY_TASK",
      confidence: "high",
    });
    expect(contrast.evidence.selectors).toEqual([".muted", "#inactive-tab"]);

    const mutation = first.findings.find((finding) => finding.tool === "mutation-js");
    expect(mutation).toMatchObject({
      ownerIssue: 807,
      priority: "P2",
      disposition: "READY_TASK",
      target: "lib/evidence-projections.ts",
    });
    expect(mutation.evidence).toMatchObject({ survived: 8, noCoverage: 6, mutationScore: 73.58 });

    const lighthouse = first.findings.find((finding) => finding.tool === "lighthouse");
    expect(lighthouse).toMatchObject({
      ownerIssue: null,
      priority: "WATCH",
      disposition: "INVESTIGATE",
    });
    expect(lighthouse.evidence).toMatchObject({ lcpMs: 5900, tbtMs: 730, unusedJavascriptBytes: 304911 });
  });

  it("writes a compact machine-readable and human-readable queue", () => {
    const dir = fixtureDir();
    writeFileSync(
      join(dir, "axe.json"),
      JSON.stringify({
        results: [
          {
            name: "workspace-mobile",
            violations: [
              {
                id: "color-contrast",
                impact: "serious",
                help: "Contrast",
                nodes: [{ target: [".transport-time-muted"] }],
              },
            ],
          },
        ],
      }),
    );

    const { report, markdownPath } = writeTriage(dir);
    expect(report.findings[0]).toMatchObject({ ownerIssue: 1211, disposition: "READY_TASK" });
    expect(markdownPath).toContain("findings.md");
  });
});
