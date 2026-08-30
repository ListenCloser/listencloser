import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const RUN_EVAL = process.env.RUN_WAVESURFER_EVAL === "true";
const CORE_SCRIPT = "public/__wavesurfer-eval/wavesurfer.min.js";
const REGIONS_SCRIPT = "public/__wavesurfer-eval/regions.min.js";

type RunResult = {
  run: number;
  baselineReadyMs: number;
  candidateReadyMs: number;
  baselineAudioRequests: number;
  candidateAudioRequests: number;
  durationSeconds: number;
  externalMediaIdentityPreserved: boolean;
  seekRatio: number;
  regionStartRatio: number;
  regionEndRatio: number;
};

function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

test.describe("WaveSurfer equal-contract evaluation", () => {
  test.skip(!RUN_EVAL, "branch-only evaluation; #688 owns the decision");

  test("compares current Waveform with pinned WaveSurfer renderer boundary", async ({ page }) => {
    test.setTimeout(180_000);

    await page.addInitScript(() => {
      const metrics: { firstSeen: number | null; loading: number | null; ready: number | null } = {
        firstSeen: null,
        loading: null,
        ready: null,
      };
      (window as any).__waveBaselineMetrics = metrics;

      const attach = () => {
        const canvas = document.querySelector<HTMLElement>('[data-testid="waveform-canvas"]');
        if (!canvas) {
          requestAnimationFrame(attach);
          return;
        }

        metrics.firstSeen = performance.now();
        const readState = () => {
          const state = canvas.getAttribute("data-waveform-state");
          if (state === "loading" && metrics.loading === null) metrics.loading = performance.now();
          if (state === "ready" && metrics.ready === null) metrics.ready = performance.now();
        };
        readState();
        new MutationObserver(readState).observe(canvas, {
          attributes: true,
          attributeFilter: ["data-waveform-state"],
        });
      };

      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", attach, { once: true });
      } else {
        attach();
      }
    });

    const audioRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/__wavesurfer-eval/real-piano.m4a")) audioRequests.push(request.url());
    });

    const runs: RunResult[] = [];

    for (let run = 1; run <= 3; run += 1) {
      await page.goto(`/eval-wavesurfer?run=${run}`);
      const baselineCanvas = page.getByTestId("waveform-canvas");
      await expect(baselineCanvas).toHaveAttribute("data-waveform-state", "ready", { timeout: 45_000 });

      const baselineMetrics = await page.evaluate(() => (window as any).__waveBaselineMetrics);
      const baselineStart = baselineMetrics.loading ?? baselineMetrics.firstSeen;
      if (baselineStart == null || baselineMetrics.ready == null) {
        throw new Error(`baseline timing markers missing for run ${run}`);
      }
      const baselineReadyMs = baselineMetrics.ready - baselineStart;

      await page.addScriptTag({ url: "/__wavesurfer-eval/wavesurfer.min.js" });
      await page.addScriptTag({ url: "/__wavesurfer-eval/regions.min.js" });

      const candidate = await page.evaluate(async (runNumber) => {
        const WaveSurfer = (window as any).WaveSurfer;
        if (!WaveSurfer?.create || !WaveSurfer?.Regions?.create) {
          throw new Error("WaveSurfer core/Regions UMD globals were not installed");
        }

        const mount = document.getElementById("wavesurfer-eval-candidate-mount");
        if (!mount) throw new Error("candidate mount missing");
        mount.replaceChildren();

        const media = document.createElement("audio");
        media.preload = "auto";
        media.src = `/__wavesurfer-eval/real-piano.m4a?candidate=${runNumber}`;
        const regions = WaveSurfer.Regions.create();
        const started = performance.now();
        const ws = WaveSurfer.create({
          container: mount,
          media,
          height: 220,
          waveColor: "#8f8a80",
          progressColor: "#ddd5c8",
          cursorColor: "#ddd5c8",
          cursorWidth: 2,
          interact: true,
          normalize: false,
          plugins: [regions],
        });

        await new Promise<void>((resolve, reject) => {
          ws.once("ready", () => resolve());
          ws.once("error", (error: unknown) => reject(error));
        });

        const result = {
          readyMs: performance.now() - started,
          durationSeconds: ws.getDuration(),
          externalMediaIdentityPreserved: ws.getMediaElement() === media,
        };
        (window as any).__wavesurferEval = { ws, regions, media };
        return result;
      }, run);

      const mount = page.locator("#wavesurfer-eval-candidate-mount");
      const box = await mount.boundingBox();
      if (!box) throw new Error("candidate mount has no layout box");

      await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
      await expect.poll(
        () => page.evaluate(() => (window as any).__wavesurferEval.ws.getCurrentTime()),
        { timeout: 5_000 },
      ).toBeGreaterThan(candidate.durationSeconds * 0.4);
      const seekTime = await page.evaluate(() => (window as any).__wavesurferEval.ws.getCurrentTime());

      await page.evaluate(() => {
        const handle = (window as any).__wavesurferEval;
        handle.regions.clearRegions();
        handle.disableDragSelection = handle.regions.enableDragSelection({
          color: "rgba(214, 181, 109, 0.18)",
        });
      });
      await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.55);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.55, { steps: 8 });
      await page.mouse.up();
      await expect.poll(
        () => page.evaluate(() => (window as any).__wavesurferEval.regions.getRegions().length),
        { timeout: 5_000 },
      ).toBe(1);

      const region = await page.evaluate(() => {
        const handle = (window as any).__wavesurferEval;
        const item = handle.regions.getRegions()[0];
        return {
          start: item.start,
          end: item.end,
          duration: handle.ws.getDuration(),
        };
      });

      const baselineAudioRequests = audioRequests.filter((url) => url.includes(`baseline=${run}`)).length;
      const candidateAudioRequests = audioRequests.filter((url) => url.includes(`candidate=${run}`)).length;

      runs.push({
        run,
        baselineReadyMs,
        candidateReadyMs: candidate.readyMs,
        baselineAudioRequests,
        candidateAudioRequests,
        durationSeconds: candidate.durationSeconds,
        externalMediaIdentityPreserved: candidate.externalMediaIdentityPreserved,
        seekRatio: seekTime / candidate.durationSeconds,
        regionStartRatio: region.start / region.duration,
        regionEndRatio: region.end / region.duration,
      });

      expect(candidate.externalMediaIdentityPreserved).toBe(true);
      expect(seekTime / candidate.durationSeconds).toBeGreaterThan(0.4);
      expect(seekTime / candidate.durationSeconds).toBeLessThan(0.6);
      expect(region.start / region.duration).toBeGreaterThan(0.16);
      expect(region.start / region.duration).toBeLessThan(0.25);
      expect(region.end / region.duration).toBeGreaterThan(0.26);
      expect(region.end / region.duration).toBeLessThan(0.36);

      await page.evaluate(() => {
        const handle = (window as any).__wavesurferEval;
        handle.disableDragSelection?.();
        handle.ws.destroy();
        delete (window as any).__wavesurferEval;
      });
    }

    const baselineMedian = median(runs.map((item) => item.baselineReadyMs));
    const candidateMedian = median(runs.map((item) => item.candidateReadyMs));
    const output = {
      schemaVersion: 1,
      candidate: {
        name: "wavesurfer.js",
        version: "7.12.8",
        license: "BSD-3-Clause",
        coreScriptBytes: statSync(CORE_SCRIPT).size,
        regionsScriptBytes: statSync(REGIONS_SCRIPT).size,
      },
      fixture: "tests/fixtures/real-piano.m4a",
      contract: {
        transportOwnership: "external HTMLMediaElement retained by ListenCloser",
        waveformRenderer: "WaveSurfer",
        selectionPrimitive: "Regions drag selection",
        productSelectionAndEvidenceSemantics: "remain adapter-owned",
      },
      currentWaveformSourceLines: readFileSync("components/Waveform.tsx", "utf8").split("\n").length,
      runs,
      summary: {
        baselineReadyMedianMs: baselineMedian,
        candidateReadyMedianMs: candidateMedian,
        candidateVsBaselineReadyRatio: candidateMedian / baselineMedian,
        baselineAudioRequestsMedian: median(runs.map((item) => item.baselineAudioRequests)),
        candidateAudioRequestsMedian: median(runs.map((item) => item.candidateAudioRequests)),
        externalMediaIdentityPreserved: runs.every((item) => item.externalMediaIdentityPreserved),
        seekContractPassed: runs.every((item) => item.seekRatio > 0.4 && item.seekRatio < 0.6),
        dragSelectionContractPassed: runs.every(
          (item) => item.regionStartRatio > 0.16 && item.regionStartRatio < 0.25 && item.regionEndRatio > 0.26 && item.regionEndRatio < 0.36,
        ),
      },
      caveats: [
        "This first gate evaluates waveform rendering/interaction only; Spectrogram remains untested until waveform earns continuation.",
        "Browser HTTP cache keys are separated with baseline/candidate query strings, but hosted-run timing remains environment-specific.",
        "Evidence annotations are representable as non-editable Regions, but product evidence focus semantics are intentionally not delegated in this gate.",
      ],
    };

    mkdirSync("artifacts", { recursive: true });
    writeFileSync("artifacts/wavesurfer-equal-contract.json", `${JSON.stringify(output, null, 2)}\n`);
  });
});
