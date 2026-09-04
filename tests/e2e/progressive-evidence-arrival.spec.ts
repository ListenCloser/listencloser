import { expect, test } from "@playwright/test";
import { mockSession, persistSessionScript, MOCK_PROJECT_REF } from "../fixtures/mockSession";

type WorkBundleLike = {
  jobs: Array<{ lifecycle: Record<string, unknown>; [key: string]: unknown }>;
  artifacts: Array<{ artifact: { kind?: string; [key: string]: unknown }; [key: string]: unknown }>;
  [key: string]: unknown;
};

function installProgressiveFindingHarness() {
  const originalFetch = window.fetch.bind(window);
  let activeJob: WorkBundleLike["jobs"][number] | null = null;
  let activeWorkPolls = 0;
  let progressiveEvidenceEnabled = false;

  const jsonResponse = (response: Response, body: unknown) => {
    const headers = new Headers(response.headers);
    headers.set("content-type", "application/json");
    headers.delete("content-length");
    return new Response(JSON.stringify(body), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };

  const earlyMidiArtifact = () => {
    const now = new Date().toISOString();
    const version = {
      id: "mock-midi-version",
      artifact_id: "artifact-mock-midi-version",
      storage_bucket: "artifacts",
      storage_key: "mock/mock-midi-version",
      parent_version_id: null,
      lineage: [],
      byte_size: 100,
      sha256: null,
      label: "mock-midi-version",
      metadata: {},
      created_at: now,
      created_by: "mock-user-1",
      produced_by_job_id: "mock-job-1",
    };
    return {
      artifact: {
        id: "artifact-mock-midi-version",
        work_id: "mock-work-1",
        kind: "midi_performance",
        mime_type: "application/octet-stream",
        created_at: now,
      },
      versions: [version],
      latest_version: version,
      signed_url: "https://example.com/mock.mid",
    };
  };

  window.fetch = async (input, init) => {
    const requestUrl = typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    const url = new URL(requestUrl, window.location.href);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const response = await originalFetch(input, init);
    if (method !== "GET") return response;

    if (url.pathname === "/api/v1/works/mock-work-1") {
      const body = await response.clone().json() as WorkBundleLike;
      if (body.jobs.length > 0) activeJob = body.jobs[0];
      if (!activeJob) return response;

      activeWorkPolls += 1;
      // Keep the job visibly active long enough to prove both sides of the
      // first-value transition. The shared MSW fixture can finish underneath;
      // this page-local harness only controls what this browser observes.
      if (activeWorkPolls < 7) {
        const original = body.artifacts.find((item) => item.artifact.kind === "audio_original")
          ?? body.artifacts[0];
        const artifacts = original ? [original] : [];
        if (activeWorkPolls >= 5) {
          artifacts.push(earlyMidiArtifact());
          progressiveEvidenceEnabled = true;
        }
        const runningJob = {
          ...activeJob,
          lifecycle: {
            ...activeJob.lifecycle,
            current: "running",
            progress: activeWorkPolls >= 5 ? 0.8 : 0.45,
          },
        };
        return jsonResponse(response, { ...body, jobs: [runningJob], artifacts });
      }

      activeJob = null;
      return response;
    }

    if (url.pathname === "/api/v1/versions/mock-midi-version/insights" && progressiveEvidenceEnabled) {
      const insights = await response.clone().json() as Array<Record<string, unknown>>;
      const nullSpan = {
        start_seconds: null,
        end_seconds: null,
        start_beat: null,
        end_beat: null,
        start_measure: null,
        end_measure: null,
      };
      return jsonResponse(response, [
        ...insights,
        {
          id: "progressive-density-insight",
          version_id: "mock-midi-version",
          kind: "rhythm_density",
          claim: "Observed note-onset density varies across the recording.",
          span: nullSpan,
          entity_ids: [],
          evidence: {
            windows: [
              { start: 0, end: 2, density: 1 },
              { start: 2, end: 4, density: 4 },
              { start: 4, end: 6, density: 1.5 },
            ],
          },
          confidence: null,
          provenance: { method: "mock_progressive_fixture" },
          created_at: new Date().toISOString(),
          created_by: "mock-user-1",
          produced_by_job_id: "mock-analysis-job",
        },
      ]);
    }

    return response;
  };
}

test("a durable recording stays usable while understand artifacts and the first finding arrive", async ({ page }) => {
  await page.addInitScript(persistSessionScript(), { projectRef: MOCK_PROJECT_REF, session: mockSession });
  await page.addInitScript(installProgressiveFindingHarness);
  await page.goto("/");
  await page.waitForFunction(
    () => navigator.serviceWorker?.controller !== null,
    undefined,
    { timeout: 15_000 },
  );
  // On the first-ever mocked page load, MSW registration can finish just after
  // the one-shot processing-health request. Reload once with the active worker
  // controlling navigation so every API precondition is deterministically mocked.
  await page.reload();

  const importButton = page.getByRole("complementary").getByRole("button", { name: "Import audio" });
  await expect(importButton).toBeVisible({ timeout: 20_000 });
  // Import is processing-dependent. Do not race the initial health check: the
  // control becomes enabled only after the queue endpoint confirms readiness.
  await expect(importButton).toBeEnabled({ timeout: 10_000 });
  await importButton.click();
  await page.getByRole("menuitem", { name: /Upload recording/ }).click();
  await expect(page.getByRole("dialog", { name: "Process recording" })).toBeVisible();
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose audio" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles({
    name: "progressive-fixture.m4a",
    mimeType: "audio/mp4",
    buffer: Buffer.from("mock progressive m4a payload"),
  });

  // Upload durability ends the blocking phase. The real source is already a
  // usable Work while the understand job is still running.
  const processingNotice = page.locator(".workspace-processing-notice");
  await expect(page.getByText("Ready to listen.", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(processingNotice).toBeVisible();
  await expect(page.getByRole("tab", { name: "Waveform" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Playback source:/ })).toBeVisible();
  await expect(page.locator(".operation-layer")).not.toBeVisible();

  // Breakdown is itself a progressive surface. While no supported evidence has
  // arrived, its canonical zero-evidence state must be visible rather than
  // hiding the entire Inspector until the workflow reaches a terminal state.
  await expect(page.getByText("Analysis is still in progress", { exact: true })).toBeVisible({ timeout: 3_000 });
  const firstFinding = page.getByText("Note-onset activity is densest in this passage.", { exact: true });
  await expect(firstFinding).not.toBeVisible();

  // The mock Work bundle initially exposes only the durable source. Keep the
  // complete representation navigation in place instead of inserting views
  // later; unavailable views are disabled until source-of-truth payloads exist.
  const representationTabs = page.getByRole("tablist", { name: "Music representation" });
  const pianoRollTab = representationTabs.getByRole("tab", { name: "Piano Roll" });
  const scoreTab = representationTabs.getByRole("tab", { name: "Score" });
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);
  await expect(pianoRollTab).toBeVisible();
  await expect(scoreTab).toBeVisible();
  await expect(pianoRollTab).toBeDisabled();
  await expect(scoreTab).toBeDisabled();

  // A persisted MIDI Version + supported temporal insight now arrives while the
  // job is deliberately still running. The first ranked finding must become a
  // real musical action immediately; workflow completion is not its visibility
  // gate.
  await expect(firstFinding).toBeVisible({ timeout: 10_000 });
  await expect(processingNotice).toBeVisible();
  const findingCard = page.locator(".inspector-breakdown-finding").filter({ hasText: "Note-onset activity is densest in this passage." });
  await expect(findingCard.getByRole("button", { name: /^Hear / })).toBeVisible();
  await expect(pianoRollTab).toBeEnabled();
  await expect(scoreTab).toBeDisabled();

  // When the backend bundle exposes the remaining durable artifacts, the same
  // navigation becomes interactive without stealing the active representation,
  // source, or already-published finding.
  await expect(scoreTab).toBeEnabled({ timeout: 10_000 });
  await expect(representationTabs.getByRole("tab")).toHaveCount(4);
  await expect(page.getByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Playback source: Original", exact: true })).toBeVisible();
  await expect(page.getByText("Ready to listen.", { exact: true })).not.toBeVisible({ timeout: 5_000 });
  await expect(firstFinding).toBeVisible();
});
