import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockSession, MOCK_PROJECT_REF, persistSessionScript } from "../fixtures/mockSession";

type TransitionResource = {
  path: string;
  initiator: string;
  duration_ms: number;
  transferred_bytes: number;
};

type TransitionTiming = {
  first_useful_pixels_ms: number;
  interaction_ready_ms: number;
  resource_requests: number;
  resource_duration_ms: number;
  transferred_bytes: number;
  resources: TransitionResource[];
  long_task_supported: boolean;
  long_task_count: number;
  long_task_duration_ms: number;
};

type PerfSnapshot = {
  start: number;
  longTaskOffset: number;
  longTaskSupported: boolean;
};

async function installLongTaskCollector(page: Page) {
  await page.addInitScript(() => {
    const target = window as typeof window & {
      __representationLongTasks?: { startTime: number; duration: number }[];
      __representationLongTaskSupported?: boolean;
    };
    target.__representationLongTasks = [];
    target.__representationLongTaskSupported = Boolean(
      "PerformanceObserver" in window
      && PerformanceObserver.supportedEntryTypes?.includes("longtask"),
    );
    if (!target.__representationLongTaskSupported) return;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        target.__representationLongTasks!.push({
          startTime: entry.startTime,
          duration: entry.duration,
        });
      }
    });
    observer.observe({ type: "longtask", buffered: true });
  });
}

async function startMeasurement(page: Page, label: string): Promise<PerfSnapshot> {
  return page.evaluate((name) => {
    const target = window as typeof window & {
      __representationLongTasks?: { startTime: number; duration: number }[];
      __representationLongTaskSupported?: boolean;
    };
    performance.clearMarks(`${name}:start`);
    performance.clearMarks(`${name}:useful`);
    performance.clearMarks(`${name}:ready`);
    performance.clearMeasures(`${name}:useful`);
    performance.clearMeasures(`${name}:ready`);
    performance.mark(`${name}:start`);
    return {
      start: performance.now(),
      longTaskOffset: target.__representationLongTasks?.length ?? 0,
      longTaskSupported: target.__representationLongTaskSupported ?? false,
    };
  }, label);
}

async function markUseful(page: Page, label: string) {
  await page.evaluate((name) => performance.mark(`${name}:useful`), label);
}

async function finishMeasurement(page: Page, label: string, snapshot: PerfSnapshot): Promise<TransitionTiming> {
  return page.evaluate(({ name, before }) => {
    const target = window as typeof window & {
      __representationLongTasks?: { startTime: number; duration: number }[];
    };
    performance.mark(`${name}:ready`);
    performance.measure(`${name}:useful`, `${name}:start`, `${name}:useful`);
    performance.measure(`${name}:ready`, `${name}:start`, `${name}:ready`);

    const resourceEntries = performance
      .getEntriesByType("resource")
      .filter((entry) => entry.startTime >= before.start) as PerformanceResourceTiming[];
    const longTasks = (target.__representationLongTasks ?? [])
      .slice(before.longTaskOffset)
      .filter((entry) => entry.startTime >= before.start);

    const round = (value: number) => Math.round(value * 10) / 10;
    const duration = (measureName: string) => performance.getEntriesByName(measureName, "measure").at(-1)?.duration ?? 0;
    const resourcePath = (entry: PerformanceResourceTiming) => {
      try {
        const url = new URL(entry.name, window.location.href);
        return `${url.pathname}${url.search}`;
      } catch {
        return entry.name;
      }
    };

    return {
      first_useful_pixels_ms: round(duration(`${name}:useful`)),
      interaction_ready_ms: round(duration(`${name}:ready`)),
      resource_requests: resourceEntries.length,
      resource_duration_ms: round(resourceEntries.reduce((total, entry) => total + entry.duration, 0)),
      transferred_bytes: resourceEntries.reduce((total, entry) => total + (entry.transferSize || 0), 0),
      resources: resourceEntries
        .map((entry) => ({
          path: resourcePath(entry),
          initiator: entry.initiatorType,
          duration_ms: round(entry.duration),
          transferred_bytes: entry.transferSize || 0,
        }))
        .sort((a, b) => b.duration_ms - a.duration_ms)
        .slice(0, 8),
      long_task_supported: before.longTaskSupported,
      long_task_count: longTasks.length,
      long_task_duration_ms: round(longTasks.reduce((total, entry) => total + entry.duration, 0)),
    };
  }, { name: label, before: snapshot });
}

async function measureTransition({
  page,
  label,
  action,
  useful,
  ready,
}: {
  page: Page;
  label: string;
  action: () => Promise<void>;
  useful: () => Promise<void>;
  ready?: () => Promise<void>;
}): Promise<TransitionTiming> {
  const snapshot = await startMeasurement(page, label);
  await action();
  await useful();
  await markUseful(page, label);
  await (ready ?? useful)();
  return finishMeasurement(page, label, snapshot);
}

async function waitForVisible(locator: Locator, timeout = 30_000) {
  await expect(locator).toBeVisible({ timeout });
}

async function waitForWorkspaceData(page: Page) {
  await expect(page.getByRole("button", { name: /^Test Work\b/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Piano Roll" })).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Score" })).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Spectrogram" })).toBeEnabled({ timeout: 20_000 });
}

test.describe("representation render timing contract (MSW)", () => {
  test.beforeEach(async ({ page }) => {
    await installLongTaskCollector(page);
    await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  });

  test("records cold and mounted representation latency with browser cost signals", async ({ page }, testInfo) => {
    // Waveform is the product's initial representation, so its cold boundary is
    // workspace navigation rather than a tab click. The other representations
    // use the exact interaction the user feels: tab click -> useful pixels ->
    // interaction-ready. Where a renderer exposes only one truthful readiness
    // boundary today, useful and ready intentionally collapse to that boundary.
    await page.goto("/");
    const waveformCanvas = page.getByTestId("waveform-canvas");
    await waitForWorkspaceData(page);
    await expect(waveformCanvas).toHaveAttribute("data-waveform-state", "ready", { timeout: 30_000 });
    const waveformInitial = await page.evaluate(() => {
      const navigation = performance.getEntriesByType("navigation")[0];
      return {
        navigation_start_to_ready_ms: Math.round(performance.now() * 10) / 10,
        navigation_entry_duration_ms: navigation ? Math.round(navigation.duration * 10) / 10 : null,
      };
    });

    const waveformTab = page.getByRole("tab", { name: "Waveform" });
    const pianoTab = page.getByRole("tab", { name: "Piano Roll" });
    const scoreTab = page.getByRole("tab", { name: "Score" });
    const spectrogramTab = page.getByRole("tab", { name: "Spectrogram" });
    const pianoRoll = page.getByTestId("piano-roll");
    const firstScoreMeasure = page.locator(".sheet-music-container g.vf-measure").first();
    const spectrogramCanvas = page.getByTestId("spectrogram-canvas");

    const pianoFirst = await measureTransition({
      page,
      label: "piano:first",
      action: () => pianoTab.click(),
      useful: () => waitForVisible(pianoRoll),
      ready: async () => {
        await waitForVisible(pianoRoll.locator("svg"));
        await expect(pianoRoll.locator("svg")).toHaveAttribute("role", "button");
      },
    });

    const waveformMounted = await measureTransition({
      page,
      label: "waveform:mounted",
      action: () => waveformTab.click(),
      useful: async () => {
        await waitForVisible(waveformCanvas);
        await expect(waveformCanvas).toHaveAttribute("data-waveform-state", "ready");
      },
    });

    const scoreFirst = await measureTransition({
      page,
      label: "score:first",
      action: () => scoreTab.click(),
      useful: () => waitForVisible(firstScoreMeasure),
      ready: async () => {
        await waitForVisible(firstScoreMeasure);
        await expect(page.locator(".sheet-music-container")).toHaveCSS("cursor", "pointer");
      },
    });

    await waveformTab.click();
    await waitForVisible(waveformCanvas);

    const scoreMounted = await measureTransition({
      page,
      label: "score:mounted",
      action: () => scoreTab.click(),
      useful: () => waitForVisible(firstScoreMeasure),
    });

    await waveformTab.click();
    await waitForVisible(waveformCanvas);

    const spectrogramFirst = await measureTransition({
      page,
      label: "spectrogram:first",
      action: () => spectrogramTab.click(),
      useful: async () => {
        await waitForVisible(spectrogramCanvas);
        await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready", { timeout: 30_000 });
      },
    });

    await waveformTab.click();
    await waitForVisible(waveformCanvas);

    const spectrogramMounted = await measureTransition({
      page,
      label: "spectrogram:mounted",
      action: () => spectrogramTab.click(),
      useful: async () => {
        await waitForVisible(spectrogramCanvas);
        await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready");
      },
    });

    const pianoMounted = await measureTransition({
      page,
      label: "piano:mounted",
      action: () => pianoTab.click(),
      useful: () => waitForVisible(pianoRoll),
      ready: () => waitForVisible(pianoRoll.locator("svg")),
    });

    const timings = {
      environment: "playwright-msw-ci",
      note: "Hosted timing is diagnostic, not an SLA. Initial Waveform is navigation-scoped; other first visits are tab-click scoped.",
      waveform: {
        initial_navigation: waveformInitial,
        mounted_revisit: waveformMounted,
      },
      piano_roll: {
        first_visit: pianoFirst,
        mounted_revisit: pianoMounted,
      },
      score: {
        first_visit: scoreFirst,
        mounted_revisit: scoreMounted,
      },
      spectrogram: {
        first_visit: spectrogramFirst,
        mounted_revisit: spectrogramMounted,
      },
    };

    console.log(`REPRESENTATION_RENDER_TIMINGS ${JSON.stringify(timings)}`);
    await testInfo.attach("representation-render-timings.json", {
      body: Buffer.from(JSON.stringify(timings, null, 2)),
      contentType: "application/json",
    });

    // Keep the lane informative instead of turning shared hosted runners into a
    // flaky millisecond gate. Product invariants remain deterministic: mounted
    // views stay ready and do not return to loading/remount states.
    await expect(pianoRoll).toBeVisible();
    await pianoTab.click();
    await expect(pianoRoll).toBeVisible();
    await spectrogramTab.click();
    await expect(spectrogramCanvas).toHaveAttribute("data-spectrogram-state", "ready");
    await scoreTab.click();
    expect(await firstScoreMeasure.count()).toBeGreaterThan(0);
  });
});
