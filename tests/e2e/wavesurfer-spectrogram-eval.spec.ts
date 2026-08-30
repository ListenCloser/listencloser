import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const RUN_EVAL = process.env.RUN_WAVESURFER_EVAL === "true";
const CORE_SCRIPT = "public/__wavesurfer-eval/wavesurfer.min.js";
const SPECTROGRAM_SCRIPT = "public/__wavesurfer-eval/spectrogram.min.js";

type RunResult = {
  run: number;
  baselineReadyMs: number;
  candidateTotalReadyMs: number;
  decodeReadyMs: number;
  pluginReadyMs: number;
  baselineAudioRequests: number;
  candidateAudioRequests: number;
  durationSeconds: number;
  sampleRate: number;
  canvasCount: number;
  clickRatio: number;
};

function median(values: number[]) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

function sourceLines(path: string) {
  return readFileSync(path, "utf8").split("\n").length;
}

test.describe("WaveSurfer Spectrogram equal-contract evaluation", () => {
  test.skip(!RUN_EVAL, "branch-only evaluation; #688 owns the decision");

  test("compares the custom FFT/raster with shared-PCM WaveSurfer Spectrogram", async ({ page }) => {
    test.setTimeout(240_000);

    await page.addInitScript(() => {
      const metrics: { firstSeen: number | null; loading: number | null; ready: number | null } = {
        firstSeen: null,
        loading: null,
        ready: null,
      };
      (window as any).__spectrogramBaselineMetrics = metrics;

      const attach = () => {
        const canvas = document.querySelector<HTMLElement>('[data-testid="spectrogram-canvas"]');
        if (!canvas) {
          requestAnimationFrame(attach);
          return;
        }
        metrics.firstSeen = performance.now();
        const readState = () => {
          const state = canvas.getAttribute("data-spectrogram-state");
          if (state === "loading" && metrics.loading === null) metrics.loading = performance.now();
          if (state === "ready" && metrics.ready === null) metrics.ready = performance.now();
        };
        readState();
        new MutationObserver(readState).observe(canvas, {
          attributes: true,
          attributeFilter: ["data-spectrogram-state"],
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
    mkdirSync("artifacts", { recursive: true });

    for (let run = 1; run <= 3; run += 1) {
      await page.goto(`/eval-wavesurfer-spectrogram?mode=baseline&run=${run}`);
      const baselineCanvas = page.getByTestId("spectrogram-canvas");
      await expect(baselineCanvas).toHaveAttribute("data-spectrogram-state", "ready", { timeout: 60_000 });
      const baselineMetrics = await page.evaluate(() => (window as any).__spectrogramBaselineMetrics);
      const baselineStart = baselineMetrics.loading ?? baselineMetrics.firstSeen;
      if (baselineStart == null || baselineMetrics.ready == null) {
        throw new Error(`baseline timing markers missing for run ${run}`);
      }
      const baselineReadyMs = baselineMetrics.ready - baselineStart;
      const baselineAudioRequests = audioRequests.filter((url) => url.includes(`specBaseline=${run}`)).length;
      expect(baselineAudioRequests).toBe(1);

      if (run === 1) {
        await baselineCanvas.screenshot({ path: "artifacts/wavesurfer-spectrogram-baseline.png" });
      }

      await page.goto(`/eval-wavesurfer-spectrogram?mode=candidate&run=${run}`);
      await page.addScriptTag({ url: "/__wavesurfer-eval/wavesurfer.min.js" });
      await page.addScriptTag({ url: "/__wavesurfer-eval/spectrogram.min.js" });

      const candidate = await page.evaluate(async (runNumber) => {
        const WaveSurfer = (window as any).WaveSurfer;
        const preparePcm = (window as any).__prepareWaveSurferSpectrogramPcm;
        if (!WaveSurfer?.create || !WaveSurfer?.Spectrogram?.create || !preparePcm) {
          throw new Error("WaveSurfer core/Spectrogram bundles or shared PCM helper are unavailable");
        }

        const waveformMount = document.getElementById("wavesurfer-spectrogram-waveform-mount");
        const spectrogramMount = document.getElementById("wavesurfer-spectrogram-mount");
        if (!waveformMount || !spectrogramMount) throw new Error("candidate mounts missing");

        const started = performance.now();
        const prepared = await preparePcm(
          `/__wavesurfer-eval/real-piano.m4a?specCandidate=${runNumber}`,
          `wavesurfer-spec-candidate-${runNumber}`,
        );
        const decodedAt = performance.now();

        const colorMap = Array.from({ length: 256 }, (_, strength) => [
          (42 + strength * 0.62) / 255,
          (38 + strength * 0.49) / 255,
          (33 + strength * 0.35) / 255,
          (strength * 0.94) / 255,
        ]);

        const spectrogram = WaveSurfer.Spectrogram.create({
          container: spectrogramMount,
          fftSamples: 2048,
          height: 420,
          labels: true,
          labelsBackground: "#1d1b18",
          labelsColor: "#aaa49a",
          labelsHzColor: "#8f8a80",
          windowFunc: "hann",
          frequencyMin: 40,
          frequencyMax: prepared.sampleRate / 2,
          scale: "logarithmic",
          gainDB: 0,
          rangeDB: 90,
          colorMap,
          useWebWorker: true,
        });

        const clickState = { ratio: null as number | null };
        spectrogram.on("click", (relativeX: number) => {
          clickState.ratio = relativeX;
        });

        const pluginReady = new Promise<void>((resolve) => spectrogram.once("ready", resolve));
        const ws = WaveSurfer.create({
          container: waveformMount,
          peaks: prepared.channels,
          duration: prepared.duration,
          height: 1,
          waveColor: "transparent",
          progressColor: "transparent",
          cursorWidth: 0,
          interact: false,
          normalize: false,
          plugins: [spectrogram],
        });
        ws.once("error", (error: unknown) => {
          throw error;
        });

        await pluginReady;
        const readyAt = performance.now();
        (window as any).__wavesurferSpectrogramEval = { ws, spectrogram, clickState };

        return {
          totalReadyMs: readyAt - started,
          decodeReadyMs: decodedAt - started,
          pluginReadyMs: readyAt - decodedAt,
          durationSeconds: prepared.duration,
          sampleRate: prepared.sampleRate,
          canvasCount: spectrogramMount.querySelectorAll("canvas").length,
        };
      }, run);

      const candidateMount = page.locator("#wavesurfer-spectrogram-mount");
      await expect(candidateMount.locator("canvas").first()).toBeVisible();
      const box = await candidateMount.boundingBox();
      if (!box) throw new Error("candidate spectrogram has no layout box");
      await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
      await expect.poll(
        () => page.evaluate(() => (window as any).__wavesurferSpectrogramEval.clickState.ratio),
        { timeout: 5_000 },
      ).toBeGreaterThan(0.4);
      const clickRatio = await page.evaluate(() => (window as any).__wavesurferSpectrogramEval.clickState.ratio as number);
      expect(clickRatio).toBeLessThan(0.6);

      const candidateAudioRequests = audioRequests.filter((url) => url.includes(`specCandidate=${run}`)).length;
      expect(candidateAudioRequests).toBe(1);
      expect(candidate.canvasCount).toBeGreaterThan(0);

      if (run === 1) {
        await candidateMount.screenshot({ path: "artifacts/wavesurfer-spectrogram-candidate.png" });
      }

      runs.push({
        run,
        baselineReadyMs,
        candidateTotalReadyMs: candidate.totalReadyMs,
        decodeReadyMs: candidate.decodeReadyMs,
        pluginReadyMs: candidate.pluginReadyMs,
        baselineAudioRequests,
        candidateAudioRequests,
        durationSeconds: candidate.durationSeconds,
        sampleRate: candidate.sampleRate,
        canvasCount: candidate.canvasCount,
        clickRatio,
      });

      await page.evaluate(() => {
        const handle = (window as any).__wavesurferSpectrogramEval;
        handle.ws.destroy();
        delete (window as any).__wavesurferSpectrogramEval;
      });
    }

    const baselineMedian = median(runs.map((item) => item.baselineReadyMs));
    const candidateMedian = median(runs.map((item) => item.candidateTotalReadyMs));
    const currentCustomLines =
      sourceLines("lib/spectrogram.ts")
      + sourceLines("lib/spectrogram-data.ts")
      + sourceLines("components/Spectrogram.tsx");

    const output = {
      schemaVersion: 1,
      candidate: {
        name: "wavesurfer.js Spectrogram",
        version: "7.12.8",
        license: "BSD-3-Clause",
        mode: "ListenCloser shared decoded PCM; no WaveSurfer audio URL",
        coreScriptBytes: statSync(CORE_SCRIPT).size,
        spectrogramScriptBytes: statSync(SPECTROGRAM_SCRIPT).size,
      },
      fixture: "tests/fixtures/real-piano.m4a",
      parityConfig: {
        fftSamples: 2048,
        windowFunc: "hann",
        frequencyMinHz: 40,
        frequencyScale: "logarithmic",
        rangeDB: 90,
        labels: true,
        useWebWorker: true,
      },
      currentCustomSpectrogramSourceLines: currentCustomLines,
      runs,
      summary: {
        baselineReadyMedianMs: baselineMedian,
        candidateTotalReadyMedianMs: candidateMedian,
        candidateVsBaselineReadyRatio: candidateMedian / baselineMedian,
        decodeReadyMedianMs: median(runs.map((item) => item.decodeReadyMs)),
        pluginReadyMedianMs: median(runs.map((item) => item.pluginReadyMs)),
        baselineAudioRequestsMedian: median(runs.map((item) => item.baselineAudioRequests)),
        candidateAudioRequestsMedian: median(runs.map((item) => item.candidateAudioRequests)),
        clickContractPassed: runs.every((item) => item.clickRatio > 0.4 && item.clickRatio < 0.6),
      },
      caveats: [
        "This gate measures current full-recording custom FFT/raster against WaveSurfer's official Spectrogram plugin on the same decoded PCM source; hosted timing is directional, not an SLO.",
        "WaveSurfer receives the full decoded Float32Array channels as pre-decoded data; v7.12.8 retains Float32Array references instead of copying them before plugin computation.",
        "Selection/evidence overlays remain ListenCloser-owned and are not delegated to the Spectrogram plugin in this gate.",
        "Screenshots are retained for visual QA of logarithmic labels and the restrained warm color family.",
      ],
    };

    writeFileSync("artifacts/wavesurfer-spectrogram.json", `${JSON.stringify(output, null, 2)}\n`);
  });
});
