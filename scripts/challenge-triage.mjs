import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import process from "node:process";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_RESULTS_DIR = "challenge-results";
const DEFAULT_OWNER_MAP = "config/challenge-owner-map.json";
const PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3, WATCH: 4 };

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function stableFingerprint(parts) {
  const normalized = parts.map((part) => String(part ?? "").trim().toLowerCase()).join("|");
  return createHash("sha256").update(normalized).digest("hex").slice(0, 16);
}

function matchingRoute(ownerMap, finding) {
  return ownerMap.routes.find((route) => {
    if (route.tool !== finding.tool || route.rule !== finding.rule) return false;
    if (route.target && route.target !== finding.target) return false;
    return true;
  });
}

function applyRoute(ownerMap, finding) {
  const route = matchingRoute(ownerMap, finding);
  return {
    priority: route?.priority ?? "WATCH",
    severity: route?.severity ?? finding.severity ?? "info",
    confidence: route?.confidence ?? finding.confidence ?? "medium",
    disposition: route?.disposition ?? "INVESTIGATE",
    ownerIssue: route?.ownerIssue ?? null,
    suggestedFix: route?.suggestedFix ?? "Inspect the evidence and route it to the smallest existing owner before changing product code.",
    verification: route?.verification ?? [],
    ...finding,
  };
}

function axeFindings(resultsDir, ownerMap) {
  const path = join(resultsDir, "axe.json");
  if (!existsSync(path)) return [];
  const report = readJson(path);
  const findings = [];

  for (const scan of report.results ?? []) {
    for (const violation of scan.violations ?? []) {
      const targets = (violation.nodes ?? []).flatMap((node) => node.target ?? []).map(String);
      const finding = applyRoute(ownerMap, {
        tool: "axe",
        rule: violation.id,
        surface: scan.name,
        target: scan.name,
        title: `${violation.help} (${scan.name})`,
        severity: violation.impact === "critical" || violation.impact === "serious" ? "high" : "medium",
        confidence: "high",
        evidence: {
          impact: violation.impact ?? "unknown",
          nodeCount: violation.nodes?.length ?? 0,
          selectors: targets,
          helpUrl: violation.helpUrl ?? null,
        },
      });
      finding.fingerprint = stableFingerprint([finding.tool, finding.rule, finding.surface]);
      findings.push(finding);
    }
  }
  return findings;
}

function stripAnsi(value) {
  const ansiEscape = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
  return value.replace(ansiEscape, "");
}

function mutationFindings(resultsDir, ownerMap) {
  const path = join(resultsDir, "mutation-js.txt");
  if (!existsSync(path)) return [];
  const text = stripAnsi(readFileSync(path, "utf8"));
  const summary = text.match(/All files\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)/);
  if (!summary) return [];

  const survivors = [...text.matchAll(/\[Survived\]\s+([^\n]+)\n([^\n]+):(\d+):(\d+)/g)].map((match) => ({
    mutation: match[1].trim(),
    file: match[2].trim(),
    line: Number(match[3]),
    column: Number(match[4]),
  }));
  const uncovered = [...text.matchAll(/\[NoCoverage\]\s+([^\n]+)\n([^\n]+):(\d+):(\d+)/g)].map((match) => ({
    mutation: match[1].trim(),
    file: match[2].trim(),
    line: Number(match[3]),
    column: Number(match[4]),
  }));
  const target = survivors[0]?.file ?? uncovered[0]?.file ?? "unknown";
  const survived = Number(summary[5]);
  const noCoverage = Number(summary[6]);
  if (survived === 0 && noCoverage === 0) return [];

  const finding = applyRoute(ownerMap, {
    tool: "mutation-js",
    rule: "surviving-mutants",
    surface: "test-policy",
    target,
    title: `${survived} surviving and ${noCoverage} uncovered mutants in ${basename(target)}`,
    severity: "medium",
    confidence: "high",
    evidence: {
      mutationScore: Number(summary[1]),
      coveredScore: Number(summary[2]),
      killed: Number(summary[3]),
      timedOut: Number(summary[4]),
      survived,
      noCoverage,
      errors: Number(summary[7]),
      survivors,
      uncovered,
    },
  });
  finding.fingerprint = stableFingerprint([finding.tool, finding.rule, finding.target]);
  return [finding];
}

function newestLighthouseJson(resultsDir) {
  const dir = join(resultsDir, "lighthouse");
  if (!existsSync(dir)) return null;
  const files = readdirSync(dir).filter((name) => name.endsWith(".json")).sort();
  return files.length ? join(dir, files.at(-1)) : null;
}

function lighthouseFindings(resultsDir, ownerMap) {
  const path = newestLighthouseJson(resultsDir);
  if (!path) return [];
  const report = readJson(path);
  const performance = report.categories?.performance?.score;
  const lcp = report.audits?.["largest-contentful-paint"]?.numericValue;
  const tbt = report.audits?.["total-blocking-time"]?.numericValue;
  const cls = report.audits?.["cumulative-layout-shift"]?.numericValue;
  const unusedJs = report.audits?.["unused-javascript"]?.details?.overallSavingsBytes;

  if (performance == null) return [];
  const finding = applyRoute(ownerMap, {
    tool: "lighthouse",
    rule: "performance-baseline",
    surface: "signed-out-landing",
    target: report.finalUrl ?? report.requestedUrl ?? "/",
    title: `Lighthouse performance baseline ${Math.round(performance * 100)}`,
    severity: performance < 0.5 ? "high" : performance < 0.9 ? "medium" : "low",
    confidence: "medium",
    evidence: {
      performance,
      accessibility: report.categories?.accessibility?.score ?? null,
      bestPractices: report.categories?.["best-practices"]?.score ?? null,
      seo: report.categories?.seo?.score ?? null,
      lcpMs: lcp ?? null,
      tbtMs: tbt ?? null,
      cls: cls ?? null,
      unusedJavascriptBytes: unusedJs ?? null,
      report: basename(path),
    },
  });
  finding.fingerprint = stableFingerprint([finding.tool, finding.rule, finding.surface]);
  return [finding];
}

function schemathesisFindings(resultsDir, ownerMap) {
  const path = join(resultsDir, "schemathesis.txt");
  if (!existsSync(path)) return [];
  const text = stripAnsi(readFileSync(path, "utf8"));
  if (!/(FAILURES|ERRORS|FAILED|failure:|error:)/i.test(text)) return [];

  const finding = applyRoute(ownerMap, {
    tool: "schemathesis",
    rule: "api-failure",
    surface: "api",
    target: "openapi",
    title: "Schemathesis produced an API counterexample",
    severity: "high",
    confidence: "medium",
    evidence: {
      excerpt: text.split("\n").filter((line) => /(FAIL|ERROR|counterexample)/i.test(line)).slice(0, 20),
    },
  });
  finding.fingerprint = stableFingerprint([finding.tool, finding.rule, finding.target]);
  return [finding];
}

function sortFindings(findings) {
  return [...findings].sort((a, b) => {
    const priority = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
    if (priority !== 0) return priority;
    return a.fingerprint.localeCompare(b.fingerprint);
  });
}

function findingLine(finding) {
  const owner = finding.ownerIssue ? `#${finding.ownerIssue}` : "unrouted";
  return `- **${finding.priority} ${finding.disposition}** \`${finding.fingerprint}\` ${finding.title} — owner ${owner}`;
}

function renderMarkdown(report) {
  const actionable = report.findings.filter((finding) => finding.disposition !== "INVESTIGATE");
  const investigate = report.findings.filter((finding) => finding.disposition === "INVESTIGATE");
  const lines = [
    "# Adversarial challenge triage",
    "",
    `Generated ${report.generatedAt}. ${report.findings.length} deduplicated finding(s).`,
    "",
    "## ACTIONABLE",
    "",
  ];

  if (actionable.length === 0) lines.push("No actionable findings.");
  for (const finding of actionable) {
    lines.push(findingLine(finding));
    lines.push(`  - evidence: ${finding.tool}/${finding.rule}; severity ${finding.severity}; confidence ${finding.confidence}`);
    lines.push(`  - next: ${finding.suggestedFix}`);
    if (finding.verification.length) lines.push(`  - prove: ${finding.verification.map((item) => `\`${item}\``).join(", ")}`);
  }

  lines.push("", "## INVESTIGATE", "");
  if (investigate.length === 0) lines.push("No investigation-only findings.");
  for (const finding of investigate) {
    lines.push(findingLine(finding));
    lines.push(`  - evidence: ${finding.tool}/${finding.rule}; severity ${finding.severity}; confidence ${finding.confidence}`);
    lines.push(`  - next: ${finding.suggestedFix}`);
  }
  lines.push("");
  return lines.join("\n");
}

export function triageResults(resultsDir = DEFAULT_RESULTS_DIR, ownerMapPath = DEFAULT_OWNER_MAP) {
  const ownerMap = readJson(ownerMapPath);
  const findings = sortFindings([
    ...axeFindings(resultsDir, ownerMap),
    ...mutationFindings(resultsDir, ownerMap),
    ...lighthouseFindings(resultsDir, ownerMap),
    ...schemathesisFindings(resultsDir, ownerMap),
  ]);
  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    findings,
  };
}

export function writeTriage(resultsDir = DEFAULT_RESULTS_DIR, ownerMapPath = DEFAULT_OWNER_MAP) {
  mkdirSync(resultsDir, { recursive: true });
  const report = triageResults(resultsDir, ownerMapPath);
  const jsonPath = join(resultsDir, "findings.json");
  const markdownPath = join(resultsDir, "findings.md");
  writeFileSync(jsonPath, `${JSON.stringify(report, null, 2)}\n`);
  writeFileSync(markdownPath, renderMarkdown(report));
  return { report, jsonPath, markdownPath };
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : null;
if (invokedPath === fileURLToPath(import.meta.url)) {
  const resultsDir = process.env.CHALLENGE_RESULTS_DIR || process.argv[2] || DEFAULT_RESULTS_DIR;
  const ownerMapPath = process.env.CHALLENGE_OWNER_MAP || DEFAULT_OWNER_MAP;
  const { report, jsonPath, markdownPath } = writeTriage(resultsDir, ownerMapPath);
  globalThis.console.log(`challenge triage: ${report.findings.length} finding(s)`);
  globalThis.console.log(`  JSON: ${jsonPath}`);
  globalThis.console.log(`  Markdown: ${markdownPath}`);
  globalThis.console.log("");
  globalThis.console.log(readFileSync(markdownPath, "utf8"));
}
