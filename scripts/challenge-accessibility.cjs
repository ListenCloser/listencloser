const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const axe = require("axe-core");

const baseURL = (globalThis.process.env.CHALLENGE_FRONTEND_URL || "http://127.0.0.1:3000").replace(
  /\/$/,
  "",
);
const resultsDir = globalThis.process.env.CHALLENGE_RESULTS_DIR || "challenge-results";

const projectRef = "cijhpddqvvzyzfzmkdnn";
const mockSession = {
  access_token: "e2e-fake-access-token",
  token_type: "bearer",
  expires_in: 3600,
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  refresh_token: "e2e-fake-refresh-token",
  user: {
    id: "00000000-0000-0000-0000-000000000001",
    email: "e2e@example.com",
    aud: "authenticated",
    role: "authenticated",
    app_metadata: {},
    user_metadata: {},
    created_at: new Date().toISOString(),
  },
};

const scans = [
  { name: "signed-out", authenticated: false, viewport: { width: 1180, height: 1000 } },
  { name: "workspace-desktop", authenticated: true, viewport: { width: 1180, height: 1000 } },
  { name: "workspace-mobile", authenticated: true, viewport: { width: 390, height: 844 } },
];

async function scan(browser, spec) {
  const context = await browser.newContext({ viewport: spec.viewport });
  try {
    if (spec.authenticated) {
      await context.addInitScript(
        ({ key, session }) => {
          globalThis.localStorage.setItem(key, JSON.stringify(session));
        },
        { key: `sb-${projectRef}-auth-token`, session: mockSession },
      );
    }

    const page = await context.newPage();
    await page.goto(`${baseURL}/`, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForTimeout(1_000);
    await page.addScriptTag({ content: axe.source });

    const result = await page.evaluate(async () => {
      return globalThis.axe.run(globalThis.document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"],
        },
      });
    });

    return {
      name: spec.name,
      url: page.url(),
      viewport: spec.viewport,
      violations: result.violations,
      incomplete: result.incomplete,
      passes: result.passes.length,
    };
  } finally {
    await context.close();
  }
}

function printViolations(result) {
  if (result.violations.length === 0) {
    globalThis.console.log(`  ✅ ${result.name}: no automated WCAG violations`);
    return;
  }

  globalThis.console.log(`  ❌ ${result.name}: ${result.violations.length} violation rule(s)`);
  for (const violation of result.violations) {
    globalThis.console.log(
      `     ${violation.id} [${violation.impact || "unknown"}] — ${violation.help}`,
    );
    for (const node of violation.nodes.slice(0, 5)) {
      globalThis.console.log(`       ${node.target.join(" ")}`);
    }
    if (violation.nodes.length > 5) {
      globalThis.console.log(`       … ${violation.nodes.length - 5} more node(s)`);
    }
  }
}

async function main() {
  fs.mkdirSync(resultsDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    for (const spec of scans) {
      const result = await scan(browser, spec);
      results.push(result);
      printViolations(result);
    }
  } finally {
    await browser.close();
  }

  const outputPath = path.join(resultsDir, "axe.json");
  fs.writeFileSync(
    outputPath,
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        baseURL,
        axeVersion: axe.version,
        results,
      },
      null,
      2,
    ),
  );
  globalThis.console.log(`  ↳ full report: ${outputPath}`);

  const violationCount = results.reduce((total, result) => total + result.violations.length, 0);
  if (violationCount > 0) {
    globalThis.process.exitCode = 1;
  }
}

main().catch((error) => {
  globalThis.console.error(error);
  globalThis.process.exitCode = 2;
});
