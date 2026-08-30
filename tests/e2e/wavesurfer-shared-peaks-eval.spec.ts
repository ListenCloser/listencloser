import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const RUN_EVAL = process.env.RUN_WAVESURFER_EVAL === "true";
const CORE_SCRIPT = "public/__wavesurfer-eval/wavesurfer.min.js";
const REGIONS_SCRIPT = "public/__wavesurfer-eval/regions.min.js";

type RunResult = {
  run: number;
  baselineReadyMs: number;
  candidateTotalReadyMs: number;
  peakPreparationMs: number;
  waveSurferMountMs: number;
  rendererAudioRequests: number;
  transportMediaRequests: number;
  peakPoints: number;
  durationSeconds: number;
  externalMediaIdentityPreserved: boolean;
  seekRatio: number;
  regionStartRatio: number;
  regionEndRatio: number;
};

function median(values: number[]) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

test.describe("WaveSurfer shared-peaks evaluation", () => {
  test.skip(!RUN_EVAL, "branch-only evaluation; #688 owns the decision");

  test("keeps ListenCloser decode ownership while WaveSurfer renders and selects", async ({ page }) => {
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

      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attach, { once: true });
      else attach();
    });

    const audioRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/__wavesurfer-eval/real-piano.m4a")) audioRequests.push(request.url());
    });

    const runs: RunResult[] = [];

    for (let run = 1; run <= 3; run += 1) {
      await page.goto(`/eval-wavesurfer?run=shared-${run}`);
      await expect(page.getByTestId("waveform-canvas")).toHaveAttribute("data-waveform-state", "ready", { timeout: 45_000 });

      const baselineMetrics = await page.evaluate(() => (window as any).__waveBaselineMetrics);
      const baselineStart = baselineMetrics.loading ?? baselineMetrics.firstSeen;
      if (baselineStart == null || baselineMetrics.ready == null) throw new Error(`baseline timing markers missing for run ${run}`);
      const baselineReadyMs = baselineMetrics.ready - baselineStart;

      await page.addScriptTag({ url: "/__wavesurfer-eval/wavesurfer.min.js" });
      await page.addScriptTag({ url: "/__wavesurfer-eval/regions.min.js" });

      const candidate = await page.evaluate(async (runNumber) => {
        const WaveSurfer = (window as any).WaveSurfer;
        const preparePeaks = (window as any).__prepareWaveSurferPeaks;
        if (!WaveSurfer?.create || !WaveSurfer?.Regions?.create || !preparePeaks) {
          throw new Error("WaveSurfer bundles or shared peak preparation are unavailable");
        }

        const mount = document.getElementById("wavesurfer-eval-candidate-mount");
        if (!mount) throw new Error("candidate mount missing");
        mount.replaceChildren();

        const rendererUrl = `/__wavesurfer-eval/real-piano.m4a?sharedRenderer=${runNumber}`;
        const media = document.createElement("audio");
        media.preload = "metadata";
        media.src = `/__wavesurfer-eval/real-piano.m4a?sharedMedia=${runNumber}`;

        const started = performance.now();
        const prepared = await preparePeaks(rendererUrl, `wavesurfer-shared-${runNumber}`);
        const preparedAt = performance.now();
        const regions = WaveSurfer.Regions.create();
        const ws = WaveSurfer.create({
          container: mount,
          media,
          peaks: prepared.peaks,
          duration: prepared.duration,
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
        const readyAt = performance.now();

        (window as any).__wavesurferSharedEval = { ws, regions, media };
        return {
          totalReadyMs: readyAt - started,
          peakPreparationMs: preparedAt - started,
          mountMs: readyAt - preparedAt,
          durationSeconds: ws.getDuration(),
          peakPoints: prepared.peakPoints,
          externalMediaIdentityPreserved: ws.getMediaElement() === media,
        };
      }, run);

      const mount = page.locator("#wavesurfer-eval-candidate-mount");
      const box = await mount.boundingBox();
      if (!box) throw new Error("candidate mount has no layout box");

      await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
      await expect.poll(
        () => page.evaluate(() => (window as any).__wavesurferSharedEval.ws.getCurrentTime()),
        { timeout: 5_000 },
      ).toBeGreaterThan(candidate.durationSeconds * 0.4);
      const seekTime = await page.evaluate(() => (window as any).__wavesurferSharedEval.ws.getCurrentTime());

      await page.evaluate(() => {
        const handle = (window as any).__wavesurferSharedEval;
        handle.disableDragSelection = handle.regions.enableDragSelection({ color: "rgba(214, 181, 109, 0.18)" });
      });
      await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.55);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.55, { steps: 8 });
      await page.mouse.up();
      await expect.poll(
        () => page.evaluate(() => (window as any).__wavesurferSharedEval.regions.getRegions().length),
        { timeout: 5_000 },
      ).toBe(1);

      const region = await page.evaluate(() => {
        const handle = (window as any).__wavesurferSharedEval;
        const item = handle.regions.getRegions()[0];
        return { start: item.start, end: item.end, duration: handle.ws.getDuration() };
      });

      const rendererAudioRequests = audioRequests.filter((url) => url.includes(`sharedRenderer=${run}`)).length;
      const transportMediaRequests = audioRequests.filter((url) => url.includes(`sharedMedia=${run}`)).length;
      const seekRatio = seekTime / candidate.durationSeconds;
      const regionStartRatio = region.start / region.duration;
      const regionEndRatio = region.end / region.duration;

      runs.push({
        run,
        baselineReadyMs,
        candidateTotalReadyMs: candidate.totalReadyMs,
        peakPreparationMs: candidate.peakPreparationMs,
        waveSurferMountMs: candidate.mountMs,
        rendererAudioRequests,
        transportMediaRequests,
        peakPoints: candidate.peakPoints,
        durationSeconds: candidate.durationSeconds,
        externalMediaIdentityPreserved: candidate.externalMediaIdentityPreserved,
        seekRatio,
        regionStartRatio,
        regionEndRatio,
      });

      expect(candidate.externalMediaIdentityPreserved).toBe(true);
      expect(rendererAudioRequests).toBe(1);
      expect(seekRatio).toBeGreaterThan(0.4);
      expect(seekRatio).toBeLessThan(0.6);
      expect(regionStartRatio).toBeGreaterThan(0.16);
      expect(regionStartRatio).toBeLessThan(0.25);
      expect(regionEndRatio).toBeGreaterThan(0.26);
      expect(regionEndRatio).toBeLessThan(0.36);

      await page.evaluate(() => {
        const handle = (window as any).__wavesurferSharedEval;
        handle.disableDragSelection?.();
        handle.ws.destroy();
        delete (window as any).__wavesurferSharedEval;
      });
    }

    const baselineMedian = median(runs.map((item) => item.baselineReadyMs));
    const candidateMedian = median(runs.map((item) => item.candidateTotalReadyMs));
    const output = {
      schemaVersion: 1,
      candidate: {
        name: "wavesurfer.js",
        version: "7.12.8",
        license: "BSD-3-Clause",
        mode: "ListenCloser shared decode cache + precomputed peaks",
        coreScriptBytes: statSync(CORE_SCRIPT).size,
        regionsScriptBytes: statSync(REGIONS_SCRIPT).size,
      },
      fixture: "tests/fixtures/real-piano.m4a",
      currentWaveformSourceLines: readFileSync("components/Waveform.tsx", "utf8").split("\n").length,
      runs,
      summary: {
        baselineReadyMedianMs: baselineMedian,
        candidateTotalReadyMedianMs: candidateMedian,
        candidateVsBaselineReadyRatio: candidateMedian / baselineMedian,
        peakPreparationMedianMs: median(runs.map((item) => item.peakPreparationMs)),
        waveSurferMountMedianMs: median(runs.map((item) => item.waveSurferMountMs)),
        rendererAudioRequestsMedian: median(runs.map((item) => item.rendererAudioRequests)),
        transportMediaRequestsMedian: median(runs.map((item) => item.transportMediaRequests)),
        externalMediaIdentityPreserved: runs.every((item) => item.externalMediaIdentityPreserved),
        seekContractPassed: runs.every((item) => item.seekRatio > 0.4 && item.seekRatio < 0.6),
        dragSelectionContractPassed: runs.every(
          (item) => item.regionStartRatio > 0.16 && item.regionStartRatio < 0.25 && item.regionEndRatio > 0.26 && item.regionEndRatio < 0.36,
        ),
      },
      caveats: [
        "Transport-media requests are reported separately because the production eval baseline does not instantiate the app transport element.",
        "Peak generation is intentionally simple and evaluation-only; production adoption would define one durable peak representation and fidelity test.",
        "Spectrogram remains out of scope until the waveform renderer boundary is decided.",
      ],
    };

    mkdirSync("artifacts", { recursive: true });
    writeFileSync("artifacts/wavesurfer-shared-peaks.json", `${JSON.stringify(output, null, 2)}\n`);
  });
});
