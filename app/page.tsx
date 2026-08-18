"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import WorkspaceShell, { type ServiceStatus } from "@/components/workspace/WorkspaceShell";
import {
  cancelJob,
  createProject,
  getEntities,
  getInsights,
  getWorkBundle,
  listProjects,
  listWorks,
  retryJob,
  startCompareWorkflow,
  startUnderstandWorkflow,
  startVariationWorkflow,
  uploadArtifact,
} from "@/lib/api-client";
import { JobObservationError, JobTerminalError, waitForJob, sanitizeJobError } from "@/lib/job-tracking";
import { supabase } from "@/lib/supabase";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { understandStageLabel, presentableTitle } from "@/lib/format";
import { buildPlaybackSources } from "@/lib/playback-sources";
import {
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

const ACCEPT = ".wav,.mp3,.m4a,.flac,.ogg,.aac,audio/*";
const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(["wav", "mp3", "m4a", "flac", "ogg", "aac"]);
type UploadStage = "idle" | "uploading" | "processing" | "disconnected" | "success" | "error";

function HomeContent({ onProjectName, serviceStatus }: { onProjectName: (name: string) => void; serviceStatus: ServiceStatus }) {
  const { user, loading } = useAuth();
  const {
    replaceRepresentations,
    setActiveWorkId,
    setInsights,
    setLoadingWork,
    setProject,
    setStudioOperation,
    setTakes,
    setWorks,
    workspace,
  } = useWorkspace();
  const transcriptionProfile = workspace.transcriptionProfile;
  const { replaceSources } = useTransport();
  const { setBpm, setTimeSignature, resetTimeline } = useTimeline();
  const [projectId, setProjectId] = useState("");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [processingWorkId, setProcessingWorkId] = useState<string | null>(null);
  const [pendingSourceVersionId, setPendingSourceVersionId] = useState<string | null>(null);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadSequenceRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const loadedWorkRef = useRef<string | null>(null);

  const loadWork = useCallback(async (workId: string) => {
    // Re-loading the *same* work (e.g. after creating a take or comparing
    // versions) must not reset the transport: the listener is still inspecting
    // the same piece, so keep the playhead and playback state.
    const preserveTransport = loadedWorkRef.current === workId;
    loadedWorkRef.current = workId;
    const sequence = ++loadSequenceRef.current;
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;
    setLoadingWork(true);
    setError(null);
    setActiveJobId(null);
    setProcessingWorkId(workId);
    setLoadWarnings([]);
    setPendingSourceVersionId(null);
    resetTimeline();
    replaceRepresentations([]);
    if (!preserveTransport) replaceSources([]);
    setInsights([]);
    setTakes([]);
    try {
      let bundle = await getWorkBundle(workId);
      if (sequence !== loadSequenceRef.current) return;
      let latestJob = bundle.jobs[0];
      const activeJob = latestJob &&
        ["queued", "claimed", "running"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;
      let observationIssue: JobObservationError | null = null;
      if (activeJob) {
        setActiveJobId(activeJob.id);
        setFilename(bundle.work.title);
        setStage("processing");
        setProgress(Math.round(activeJob.lifecycle.progress * 100));
        setMessage(understandStageLabel(activeJob.lifecycle.progress));
        try {
          await waitForJob(activeJob.id, (current) => {
            if (sequence !== loadSequenceRef.current) return;
            setMessage(understandStageLabel(current.progress));
            setProgress(Math.round(current.progress * 100));
          }, { signal });
        } catch (cause) {
          // Terminal jobs can still have useful partial artifacts. Re-fetch the
          // bundle and render those before presenting retry controls.
          if (cause instanceof DOMException && cause.name === "AbortError") return;
          if (cause instanceof JobObservationError) observationIssue = cause;
          else if (!(cause instanceof JobTerminalError)) throw cause;
        }
        if (!observationIssue) {
          bundle = await getWorkBundle(workId);
          if (sequence !== loadSequenceRef.current) return;
          latestJob = bundle.jobs[0];
          setActiveJobId(null);
        }
      }
      const terminalJob = latestJob &&
        ["failed", "cancelled"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;
      const latestByKind = new Map<string, (typeof bundle.artifacts)[number]>();
      for (const item of bundle.artifacts) {
        if (
          item.latest_version &&
          item.signed_url &&
          !latestByKind.has(item.artifact.kind)
        ) {
          latestByKind.set(item.artifact.kind, item);
        }
      }
      const original = latestByKind.get("audio_original");
      const baseMidi = latestByKind.get("midi_performance");
      const midi = baseMidi ?? latestByKind.get("midi_corrected");
      const score = latestByKind.get("musicxml_score");
      const renderedScore = latestByKind.get("rendered_score");

      const takeArtifacts = bundle.artifacts.filter((item) =>
        item.latest_version && item.signed_url && ["midi_performance", "midi_corrected"].includes(item.artifact.kind),
      );
      const takes = takeArtifacts.flatMap((item) => item.latest_version ? [{
        versionId: item.latest_version.id,
        label: item.artifact.kind === "midi_performance"
          ? "Transcription"
          : item.latest_version.label || "Derived take",
        parentVersionId: item.latest_version.parent_version_id,
      }] : []);
      setTakes(takes);
      const renderedArtifacts = bundle.artifacts.filter((item) =>
        item.latest_version && item.signed_url && item.artifact.kind === "audio_rendered",
      );
      // Prefer the render that corresponds to the primary transcription, then
      // fall back to the first available render. Human labels are used so
      // internal artifact/version identifiers never surface in the UI.
      const primaryRendered = renderedArtifacts.find(
        (item) => item.latest_version?.parent_version_id === baseMidi?.latest_version?.id,
      ) ?? renderedArtifacts.find(
        (item) => item.latest_version?.parent_version_id === midi?.latest_version?.id,
      ) ?? renderedArtifacts[0];

      const extraRendered = renderedArtifacts.filter(
        (item) => item.latest_version && item.signed_url && item.latest_version.id !== primaryRendered?.latest_version?.id,
      );
      const { sources, activeId } = buildPlaybackSources({
        original: original?.latest_version && original.signed_url ? { id: original.latest_version.id, url: original.signed_url } : null,
        transcription: primaryRendered?.latest_version && primaryRendered.signed_url ? { id: primaryRendered.latest_version.id, url: primaryRendered.signed_url } : null,
        extraTakes: extraRendered.map((item) => ({ id: item.latest_version!.id, url: item.signed_url! })),
        score: renderedScore?.latest_version && renderedScore.signed_url ? { id: renderedScore.latest_version.id, url: renderedScore.signed_url } : null,
      });

      const representations: RepresentationEntry[] = [];
      if (original?.signed_url) {
        representations.push({
          kind: "waveform",
          label: "Waveform",
          sourceUrl: original.signed_url,
          sourceLabel: "Playback source",
          confidence: null,
          provenance: "uploaded source",
          audioUrl: original.signed_url,
          versionId: original.latest_version?.id,
        });
      }

      const warnings: string[] = [];
      let pendingInsights: Awaited<ReturnType<typeof getInsights>> = [];
      let pendingTempo: number | null = null;
      let pendingSignature: { numerator: number; denominator: number } | null = null;
      if (midi?.latest_version) {
        const [entitiesResult, insightsResult] = await Promise.allSettled([
          getEntities(midi.latest_version.id),
          getInsights(midi.latest_version.id),
        ]);
        if (sequence !== loadSequenceRef.current) return;
        const entities = entitiesResult.status === "fulfilled" ? entitiesResult.value : [];
        const insights = insightsResult.status === "fulfilled" ? insightsResult.value : [];
        if (entitiesResult.status === "rejected") warnings.push("The note-level piano roll could not be loaded.");
        if (insightsResult.status === "rejected") warnings.push("The saved analysis could not be loaded.");
        pendingInsights = insights;
        const notes = entities.flatMap((entity) => entity.note ? [{
          id: entity.id,
          pitch: entity.note.pitch,
          start: entity.note.start_seconds,
          end: entity.note.end_seconds,
          velocity: entity.note.velocity,
        }] : []);
        if (notes.length > 0) {
          representations.push({
            kind: "piano_roll",
            label: "Piano Roll",
            sourceUrl: midi.signed_url ?? "",
            sourceLabel: `${notes.length} detected notes`,
            confidence: null,
            provenance: "transcription",
            notes,
            versionId: midi.latest_version.id,
          });
        }
        const tempo = insights.find((item) => item.kind === "tempo")?.evidence.bpm;
        if (typeof tempo === "number" && tempo > 0) pendingTempo = tempo;
        const signature = insights.find((item) => item.kind === "time_signature")?.evidence;
        if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
          pendingSignature = { numerator: signature.numerator, denominator: signature.denominator };
        }
      }

      if (score?.signed_url) {
        try {
          const response = await fetch(score.signed_url);
          if (!response.ok) throw new Error("score request failed");
          const musicxml = await response.text();
          if (sequence !== loadSequenceRef.current) return;
          const measureStarts = (renderedScore?.latest_version?.metadata?.measure_starts_seconds as number[] | undefined) ?? [];
          representations.push({
            kind: "score",
            label: "Score",
            sourceUrl: score.signed_url,
            sourceLabel: "Quantized notation draft · review by ear",
            confidence: null,
            provenance: "music21 notation",
            musicxml,
            measureStarts,
            versionId: score.latest_version?.id,
          });
        } catch {
          warnings.push("The saved score could not be loaded.");
        }
      }

      replaceSources(sources, activeId ?? undefined, preserveTransport);
      replaceRepresentations(representations);
      setInsights(pendingInsights);
      if (pendingTempo !== null) setBpm(pendingTempo);
      if (pendingSignature !== null) setTimeSignature(pendingSignature.numerator, pendingSignature.denominator);
      setLoadWarnings(warnings);
      if (observationIssue) {
        setProcessingWorkId(workId);
        setError(observationIssue.message);
        setStage("disconnected");
      } else if (terminalJob) {
        setActiveJobId(terminalJob.id);
        setError(
          sanitizeJobError(
            terminalJob.error || terminalJob.lifecycle.message || `Understanding audio ${terminalJob.lifecycle.current}`,
          ),
        );
        setStage("error");
      } else if (original?.latest_version && !midi && !score) {
        // Source audio is safe but transcription hasn't produced artifacts yet.
        // This is a legitimate "not yet analyzed" state, not a failure.
        setPendingSourceVersionId(original.latest_version.id);
        setProcessingWorkId(null);
        setError(null);
        warnings.push("Music understanding has not completed yet. Run Analyze to transcribe this work.");
        setLoadWarnings(warnings);
        setStage("success");
      } else if (representations.length === 0) {
        // No playable artifacts at all — an empty work, not an error.
        setError(null);
        warnings.push("This work has no playable artifacts yet.");
        setLoadWarnings(warnings);
        setStage("success");
      } else {
        setActiveJobId(null);
        setStage("success");
      }
    } catch (cause) {
      if (sequence !== loadSequenceRef.current) return;
      setError(cause instanceof Error ? cause.message : "Could not load this work");
      setStage("error");
    } finally {
      if (sequence === loadSequenceRef.current) setLoadingWork(false);
    }
  }, [replaceRepresentations, replaceSources, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature, resetTimeline]);

  // Abort any in-flight job polling when the active work is deleted (activeWorkId
  // becomes null without a new loadWork) and on unmount.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (workspace.activeWorkId === null) {
      abortRef.current?.abort();
    }
  }, [workspace.activeWorkId]);

  const handledStudioAction = useRef(0);
  useEffect(() => {
    const action = workspace.studioAction;
    if (!action || action.id === handledStudioAction.current || !projectId || !workspace.activeWorkId) return;
    handledStudioAction.current = action.id;
    const workId = workspace.activeWorkId;
    void (async () => {
      const label = action.kind === "variation" ? "Creating a playable take" : "Comparing saved takes";
      setStudioOperation({ state: "running", label, message: "Queued on the music worker" });
      try {
        const result = action.kind === "variation"
          ? await startVariationWorkflow(action.versionIds[0], projectId, action.semitones ?? 0)
          : await startCompareWorkflow(action.versionIds[0], action.versionIds[1], projectId);
        await waitForJob(result.job.id, (current) => {
          setStudioOperation({ state: "running", label, message: current.message || "Working" });
        });
        await loadWork(workId);
        setStudioOperation({
          state: "success",
          label: action.kind === "variation" ? "New take is ready" : "Comparison is ready",
          message: action.kind === "variation" ? "Playback, score, and analysis have been saved with the new take." : "The comparison was saved in the analysis for the first selected take.",
        });
      } catch (cause) {
        const disconnected = cause instanceof JobObservationError;
        setStudioOperation({
          state: disconnected ? "disconnected" : "error",
          label: disconnected ? "Connection interrupted" : "Studio operation failed",
          message: cause instanceof Error ? cause.message : "Please try again.",
        });
      }
    })();
  }, [loadWork, projectId, setStudioOperation, workspace.activeWorkId, workspace.studioAction]);

  useEffect(() => {
    let cancelled = false;
    if (loading || !user) {
      setProjectId("");
      setProject(null);
      return;
    }
    void (async () => {
      try {
        const projects = await listProjects();
        const project = projects.find((item) => !item.archived_at) ??
          await createProject("Music Lab", "Audio transformations and analysis");
        const works = await listWorks(project.id);
        if (!cancelled) {
          setProjectId(project.id);
          setProject(project);
          setWorks(works);
          onProjectName(project.name);
          if (works[0]) setActiveWorkId(works[0].id);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load the project");
          setStage("error");
        }
      }
    })();
    return () => { cancelled = true; };
  }, [loading, onProjectName, setActiveWorkId, setProject, setWorks, user]);

  useEffect(() => {
    if (workspace.activeWorkId) void loadWork(workspace.activeWorkId);
  }, [loadWork, workspace.activeWorkId]);

  useEffect(() => {
    if (workspace.importRequestId > 0) fileInputRef.current?.click();
  }, [workspace.importRequestId]);

  const handleFile = useCallback(async (file: File) => {
    if (!projectId) {
      setError("Your project is still loading. Please try again in a moment.");
      setStage("error");
      return;
    }
    if (serviceStatus !== "ready") {
      setError("The processing service is offline. Your file was not uploaded.");
      setStage("error");
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.has(extension)) {
      setError("Choose a WAV, MP3, M4A, FLAC, OGG, or AAC audio file.");
      setStage("error");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("Audio files must be 4 MB or smaller.");
      setStage("error");
      return;
    }
    setFilename(file.name);
    setPendingSourceVersionId(null);
    setStage("uploading");
    setProgress(2);
    setError(null);
    try {
      const { artifact, version } = await uploadArtifact(projectId, file);
      setPendingSourceVersionId(version.id);
      setProcessingWorkId(artifact.work_id);
      setWorks(await listWorks(projectId));
      setStage("processing");
      const { job } = await startUnderstandWorkflow(version.id, projectId, transcriptionProfile);
      setActiveJobId(job.id);
      await waitForJob(job.id, (current) => {
        setMessage(understandStageLabel(current.progress));
        setProgress(5 + Math.round(current.progress * 90));
      });
      const works = await listWorks(projectId);
      setWorks(works);
      setProgress(100);
      setActiveJobId(null);
      setActiveWorkId(artifact.work_id);
      setProcessingWorkId(null);
      setPendingSourceVersionId(null);
    } catch (cause) {
      if (cause instanceof JobObservationError) {
        setError(cause.message);
        setStage("disconnected");
      } else {
        setError(cause instanceof Error ? cause.message : "Import failed");
        setStage("error");
      }
    }
  }, [projectId, serviceStatus, setActiveWorkId, setWorks]);

  const cancelActiveJob = useCallback(async () => {
    if (!activeJobId) return;
    setMessage("Cancelling after the current processing step");
    try {
      await cancelJob(activeJobId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not cancel the job");
      setStage("error");
    }
  }, [activeJobId]);

  const retryActiveJob = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!activeJobId || !workId) return;
    setStage("processing");
    setError(null);
    setProgress(0);
    try {
      const retried = await retryJob(activeJobId);
      setActiveJobId(retried.id);
      await waitForJob(retried.id, (current) => {
        setMessage(understandStageLabel(current.progress));
        setProgress(Math.round(current.progress * 100));
      });
      setActiveJobId(null);
      if (workspace.activeWorkId === workId) await loadWork(workId);
      else setActiveWorkId(workId);
      setProcessingWorkId(null);
    } catch (cause) {
      if (cause instanceof JobObservationError) {
        setError(cause.message);
        setStage("disconnected");
      } else {
        setError(cause instanceof Error ? cause.message : "Retry failed");
        setStage("error");
      }
    }
  }, [activeJobId, loadWork, processingWorkId, setActiveWorkId, workspace.activeWorkId]);

  const resumeActiveJob = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!activeJobId || !workId) return;
    setStage("processing");
    setError(null);
    try {
      await waitForJob(activeJobId, (current) => {
        setMessage(understandStageLabel(current.progress));
        setProgress(Math.round(current.progress * 100));
      });
      setActiveJobId(null);
      await loadWork(workId);
    } catch (cause) {
      if (cause instanceof JobTerminalError) {
        setError(cause.message);
        setStage("error");
      } else {
        setError(cause instanceof Error ? cause.message : "Could not reconnect to this job");
        setStage("disconnected");
      }
    }
  }, [activeJobId, loadWork, processingWorkId, workspace.activeWorkId]);

  const startPendingProcessing = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!pendingSourceVersionId || !projectId || !workId) return;
    setStage("processing");
    setError(null);
    setProgress(0);
    try {
      const { job } = await startUnderstandWorkflow(pendingSourceVersionId, projectId, transcriptionProfile);
      setActiveJobId(job.id);
      await waitForJob(job.id, (current) => {
        setMessage(understandStageLabel(current.progress));
        setProgress(Math.round(current.progress * 100));
      });
      setActiveJobId(null);
      setPendingSourceVersionId(null);
      await loadWork(workId);
    } catch (cause) {
      if (cause instanceof JobObservationError) {
        setError(cause.message);
        setStage("disconnected");
      } else {
        setError(cause instanceof Error ? cause.message : "Could not start processing");
        setStage("error");
      }
    }
  }, [loadWork, pendingSourceVersionId, processingWorkId, projectId, workspace.activeWorkId]);

  const showOverlay =
    stage === "processing" ||
    stage === "uploading" ||
    stage === "disconnected" ||
    stage === "error";

  return (
    <>
      <input
        id="audio-import-input"
        ref={fileInputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void handleFile(file);
        }}
      />
      {showOverlay && (
        <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, pointerEvents: "none" }}>
          <div style={{ pointerEvents: "auto", maxWidth: 480, width: "100%", padding: "var(--s-4)" }}>
            {(stage === "uploading" || stage === "processing") && (
              <div className="piece-processing-card" role="status">
                <span className="piece-processing-filename">{presentableTitle(filename)}</span>
                <progress value={progress} max={100} style={{ width: "100%" }} />
                <span className="piece-processing-stage">{stage === "uploading" ? "Uploading your recording…" : message} · {Math.round(progress)}%</span>
                <span className="piece-processing-hint">You can close this page; processing will continue on the server.</span>
                {stage === "processing" && activeJobId && (
                  <button className="btn" onClick={() => void cancelActiveJob()}>
                    Cancel processing
                  </button>
                )}
              </div>
            )}
            {stage === "disconnected" && (
              <div className="operation-card operation-card-warning" role="alert">
                <strong>Connection interrupted</strong><span>{error}</span>
                <span>The durable server job has not been duplicated or restarted.</span>
                <button className="btn btn-primary" onClick={() => void resumeActiveJob()}>
                  Reconnect to job
                </button>
              </div>
            )}
            {stage === "error" && (
              <div style={{ background: "var(--danger-soft)", border: "1px solid var(--danger)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)", color: "var(--danger)" }}>
                <strong>Operation failed</strong><span>{error}</span>
                <div style={{ display: "flex", gap: "var(--s-2)" }}>
                  {activeJobId && (
                    <button className="btn btn-primary" onClick={() => void retryActiveJob()}>
                      Retry processing
                    </button>
                  )}
                  {!activeJobId && pendingSourceVersionId && (
                    <button className="btn btn-primary" onClick={() => void startPendingProcessing()}>
                      Process saved audio
                    </button>
                  )}
                  <button className="btn" onClick={() => { setStage("idle"); setError(null); setProgress(0); }}>
                    {workspace.representations.length ? "Dismiss" : "Try another file"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {loadWarnings.length > 0 && stage === "success" && (
        <div className="workspace-notice" role="status">
          <strong>Some saved results need attention</strong>
          <span>{loadWarnings.join(" ")}</span>
          <button type="button" className="icon-btn" aria-label="Dismiss notice" onClick={() => setLoadWarnings([])}>✕</button>
        </div>
      )}
    </>
  );
}

export default function Home() {
  const { user } = useAuth();
  const [projectName, setProjectName] = useState("");
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>("checking");
  const healthSequence = useRef(0);

  const refreshService = useCallback(() => {
    const sequence = ++healthSequence.current;
    setServiceStatus("checking");
    void fetch("/api/health/queue", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("service unavailable");
        const body = await response.json();
        if (body.status !== "ready") throw new Error("service unavailable");
        if (sequence === healthSequence.current) setServiceStatus("ready");
      })
      .catch(() => {
        if (sequence === healthSequence.current) setServiceStatus("unavailable");
      });
  }, []);

  useEffect(() => {
    refreshService();
    const timer = window.setInterval(refreshService, 30_000);
    const onControllerChange = () => refreshService();
    navigator.serviceWorker?.addEventListener("controllerchange", onControllerChange);
    return () => {
      window.clearInterval(timer);
      navigator.serviceWorker?.removeEventListener("controllerchange", onControllerChange);
    };
  }, [refreshService]);
  if (!user) return <SignedOutLanding serviceStatus={serviceStatus} />;

  return (
    <WorkspaceShell signedIn={Boolean(user)} projectName={projectName} serviceStatus={serviceStatus}>
      <HomeContent onProjectName={setProjectName} serviceStatus={serviceStatus} />
    </WorkspaceShell>
  );
}

function SignedOutLanding({ serviceStatus }: { serviceStatus: ServiceStatus }) {
  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <main className="welcome-page">
      <header className="welcome-header"><span className="brand"><span className="brand-dot" />Music Lab</span><span>{serviceStatus === "ready" ? "Processing is ready" : "Music workspace"}</span></header>
      <section className="welcome-hero">
        <p className="piece-eyebrow">A place to listen closely</p>
        <h1>See what your music is doing.</h1>
        <p>Bring in a recording, compare the original with its transcription, and inspect a piano roll, notation, and musical analysis in one place.</p>
        <button className="btn btn-primary" onClick={signIn}>Sign in with Google</button>
        <small>Your recordings and their transcriptions stay private to your account.</small>
      </section>
      <section className="welcome-steps" aria-label="How Music Lab works"><div><b>01</b><span>Import audio</span></div><div><b>02</b><span>Listen & compare</span></div><div><b>03</b><span>Inspect the music</span></div></section>
    </main>
  );
}
