"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import BrandMark from "@/components/BrandMark";
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

function HomeContent({ serviceStatus }: { serviceStatus: ServiceStatus }) {
  const { user } = useAuth();
  const {
    replaceRepresentations,
    setActiveWorkId,
    setAnalysisState,
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
    setAnalysisState("idle");

    try {
      let bundle = await getWorkBundle(workId);
      if (sequence !== loadSequenceRef.current) return;
      let latestJob = bundle.jobs[0];
      const activeJob = latestJob && ["queued", "claimed", "running"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;
      let observationIssue: JobObservationError | null = null;

      if (activeJob) {
        setActiveJobId(activeJob.id);
        setAnalysisState("analyzing");
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

      const terminalJob = latestJob && ["failed", "cancelled"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;
      const latestByKind = new Map<string, (typeof bundle.artifacts)[number]>();
      for (const item of bundle.artifacts) {
        if (item.latest_version && item.signed_url && !latestByKind.has(item.artifact.kind)) {
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
      setTakes(takeArtifacts.flatMap((item) => item.latest_version ? [{
        versionId: item.latest_version.id,
        label: item.artifact.kind === "midi_performance" ? "Transcription" : item.latest_version.label || "Derived take",
        parentVersionId: item.latest_version.parent_version_id,
      }] : []));

      const renderedArtifacts = bundle.artifacts.filter((item) =>
        item.latest_version && item.signed_url && item.artifact.kind === "audio_rendered",
      );
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

      // First meaningful paint: once the durable bundle returns, show playable
      // audio immediately. Note entities, analysis, and MusicXML can hydrate in
      // parallel instead of holding the entire workspace behind a loading view.
      replaceSources(sources, activeId ?? undefined, preserveTransport);
      if (representations.length > 0) {
        replaceRepresentations([...representations]);
        setLoadingWork(false);
      }

      const midiVersionId = midi?.latest_version?.id ?? null;
      const [entitiesResult, insightsResult, scoreResult] = await Promise.allSettled([
        midiVersionId ? getEntities(midiVersionId) : Promise.resolve([]),
        midiVersionId ? getInsights(midiVersionId) : Promise.resolve([]),
        score?.signed_url
          ? fetch(score.signed_url).then(async (response) => {
              if (!response.ok) throw new Error("score request failed");
              return response.text();
            })
          : Promise.resolve(null),
      ]);
      if (sequence !== loadSequenceRef.current) return;

      const warnings: string[] = [];
      const entities = entitiesResult.status === "fulfilled" ? entitiesResult.value : [];
      const pendingInsights = insightsResult.status === "fulfilled" ? insightsResult.value : [];
      if (midiVersionId && entitiesResult.status === "rejected") warnings.push("Piano roll data is temporarily unavailable.");
      if (midiVersionId && insightsResult.status === "rejected") warnings.push("Analysis is temporarily unavailable.");

      const notes = entities.flatMap((entity) => entity.note ? [{
        id: entity.id,
        pitch: entity.note.pitch,
        start: entity.note.start_seconds,
        end: entity.note.end_seconds,
        velocity: entity.note.velocity,
      }] : []);
      if (midiVersionId && notes.length > 0) {
        representations.push({
          kind: "piano_roll",
          label: "Piano Roll",
          sourceUrl: midi?.signed_url ?? "",
          sourceLabel: `${notes.length} detected notes`,
          confidence: null,
          provenance: "transcription",
          notes,
          versionId: midiVersionId,
        });
      }

      let pendingTempo: number | null = null;
      let pendingSignature: { numerator: number; denominator: number } | null = null;
      const tempo = pendingInsights.find((item) => item.kind === "tempo")?.evidence.bpm;
      if (typeof tempo === "number" && tempo > 0) pendingTempo = tempo;
      const signature = pendingInsights.find((item) => item.kind === "time_signature")?.evidence;
      if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
        pendingSignature = { numerator: signature.numerator, denominator: signature.denominator };
      }

      if (score?.signed_url) {
        if (scoreResult.status === "fulfilled" && scoreResult.value) {
          const measureStarts = (renderedScore?.latest_version?.metadata?.measure_starts_seconds as number[] | undefined) ?? [];
          representations.push({
            kind: "score",
            label: "Score",
            sourceUrl: score.signed_url,
            sourceLabel: "Notation draft",
            confidence: null,
            provenance: "music21 notation",
            musicxml: scoreResult.value,
            measureStarts,
            versionId: score.latest_version?.id,
          });
        } else if (scoreResult.status === "rejected") {
          warnings.push("Score data is temporarily unavailable.");
        }
      }

      replaceRepresentations(representations);
      setInsights(pendingInsights);
      if (pendingTempo !== null) setBpm(pendingTempo);
      if (pendingSignature !== null) setTimeSignature(pendingSignature.numerator, pendingSignature.denominator);
      setLoadWarnings(warnings);

      if (observationIssue) {
        setAnalysisState("analyzing");
        setProcessingWorkId(workId);
        setError(observationIssue.message);
        setStage("disconnected");
      } else if (terminalJob) {
        setAnalysisState("completed");
        setActiveJobId(terminalJob.id);
        setError(sanitizeJobError(terminalJob.error || terminalJob.lifecycle.message || `Understanding audio ${terminalJob.lifecycle.current}`));
        setStage("error");
      } else if (original?.latest_version && !midi && !score) {
        setAnalysisState("idle");
        setPendingSourceVersionId(original.latest_version.id);
        setProcessingWorkId(null);
        setError(null);
        setStage("success");
      } else if (representations.length === 0) {
        setAnalysisState("idle");
        setError(null);
        setStage("success");
      } else {
        setAnalysisState("completed");
        setActiveJobId(null);
        setStage("success");
      }
    } catch (cause) {
      if (sequence !== loadSequenceRef.current) return;
      setError(cause instanceof Error ? cause.message : "Could not load this recording");
      setStage("error");
    } finally {
      if (sequence === loadSequenceRef.current) setLoadingWork(false);
    }
  }, [replaceRepresentations, replaceSources, resetTimeline, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

  useEffect(() => {
    if (workspace.activeWorkId === null) abortRef.current?.abort();
  }, [workspace.activeWorkId]);

  const handledStudioAction = useRef(0);
  useEffect(() => {
    const action = workspace.studioAction;
    if (!action || action.id === handledStudioAction.current || !projectId || !workspace.activeWorkId) return;
    handledStudioAction.current = action.id;
    const workId = workspace.activeWorkId;
    void (async () => {
      const label = action.kind === "variation" ? "Creating a playable take" : "Comparing saved takes";
      setStudioOperation({ state: "running", label, message: "Queued" });
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
          message: action.kind === "variation" ? "The new take is ready to audition." : "Comparison is ready.",
        });
      } catch (cause) {
        const disconnected = cause instanceof JobObservationError;
        setStudioOperation({
          state: disconnected ? "disconnected" : "error",
          label: disconnected ? "Connection interrupted" : "Operation failed",
          message: cause instanceof Error ? cause.message : "Please try again.",
        });
      }
    })();
  }, [loadWork, projectId, setStudioOperation, workspace.activeWorkId, workspace.studioAction]);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setProjectId("");
      setProject(null);
      setLoadingWork(false);
      return;
    }

    setLoadingWork(true);
    void (async () => {
      try {
        const projects = await listProjects();
        const project = projects.find((item) => !item.archived_at) ?? await createProject("Library", "Music workspace");
        const works = await listWorks(project.id);
        if (cancelled) return;
        setProjectId(project.id);
        setProject(project);
        setWorks(works);
        if (works[0]) setActiveWorkId(works[0].id);
        else setLoadingWork(false);
      } catch (cause) {
        if (!cancelled) {
          setLoadingWork(false);
          setError(cause instanceof Error ? cause.message : "Could not load your library");
          setStage("error");
        }
      }
    })();
    return () => { cancelled = true; };
  }, [setActiveWorkId, setLoadingWork, setProject, setWorks, user]);

  useEffect(() => {
    if (workspace.activeWorkId) void loadWork(workspace.activeWorkId);
  }, [loadWork, workspace.activeWorkId]);

  useEffect(() => {
    if (workspace.importRequestId > 0) fileInputRef.current?.click();
  }, [workspace.importRequestId]);

  const handleFile = useCallback(async (file: File) => {
    if (!projectId) {
      setError("Your library is still loading.");
      setStage("error");
      return;
    }
    if (serviceStatus === "unavailable") {
      setError("Audio processing is temporarily unavailable. Your file was not uploaded.");
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
      setWorks(await listWorks(projectId));
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
  }, [projectId, serviceStatus, setActiveWorkId, setWorks, transcriptionProfile]);

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
  }, [loadWork, pendingSourceVersionId, processingWorkId, projectId, transcriptionProfile, workspace.activeWorkId]);

  const showOverlay = stage === "processing" || stage === "uploading" || stage === "disconnected" || stage === "error";

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
        <div className="operation-layer">
          <div className="operation-layer-inner">
            {(stage === "uploading" || stage === "processing") && (
              <div className="piece-processing-card" role="status">
                <span className="piece-processing-filename">{presentableTitle(filename)}</span>
                <progress value={progress} max={100} />
                <span className="piece-processing-stage">{stage === "uploading" ? "Uploading…" : message} · {Math.round(progress)}%</span>
                {stage === "processing" && activeJobId && <button className="btn" onClick={() => void cancelActiveJob()}>Cancel</button>}
              </div>
            )}
            {stage === "disconnected" && (
              <div className="operation-card operation-card-warning" role="alert">
                <strong>Connection interrupted</strong><span>{error}</span>
                <button className="btn btn-primary" onClick={() => void resumeActiveJob()}>Reconnect</button>
              </div>
            )}
            {stage === "error" && (
              <div className="operation-card operation-card-error" role="alert">
                <strong>Couldn’t complete that</strong><span>{error}</span>
                <div className="operation-card-actions">
                  {activeJobId && <button className="btn btn-primary" onClick={() => void retryActiveJob()}>Retry</button>}
                  {!activeJobId && pendingSourceVersionId && <button className="btn btn-primary" onClick={() => void startPendingProcessing()}>Process saved audio</button>}
                  <button className="btn" onClick={() => { setStage("idle"); setError(null); setProgress(0); }}>Dismiss</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {loadWarnings.length > 0 && stage === "success" && (
        <div className="workspace-notice" role="status">
          <span>{loadWarnings.join(" ")}</span>
          <button type="button" className="icon-btn" aria-label="Dismiss notice" onClick={() => setLoadWarnings([])}>×</button>
        </div>
      )}
    </>
  );
}

export default function Home() {
  const { user, loading } = useAuth();
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>("checking");
  const healthSequence = useRef(0);

  const refreshService = useCallback(() => {
    const sequence = ++healthSequence.current;
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

  if (loading) return <AppBootShell />;
  if (!user) return <SignedOutLanding />;

  return (
    <WorkspaceShell signedIn serviceStatus={serviceStatus}>
      <HomeContent serviceStatus={serviceStatus} />
    </WorkspaceShell>
  );
}

function AppBootShell() {
  return (
    <main className="app-boot-shell" aria-busy="true" aria-label="Opening your library">
      <header className="app-boot-header"><BrandMark size={21} /></header>
      <div className="app-boot-workspace" aria-hidden="true">
        <aside className="app-boot-library">
          <span className="boot-line boot-line-short" />
          <span className="boot-row" /><span className="boot-row" /><span className="boot-row" />
        </aside>
        <section className="app-boot-canvas">
          <div className="app-boot-tabs"><span /><span /><span /><span /></div>
          <div className="app-boot-visual">{Array.from({ length: 8 }).map((_, index) => <span key={index} />)}</div>
        </section>
        <aside className="app-boot-inspector"><span className="boot-line" /><span className="boot-row" /><span className="boot-row" /></aside>
      </div>
      <footer className="app-boot-transport" />
    </main>
  );
}

function SignedOutLanding() {
  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <main className="welcome-page welcome-page-v4">
      <header className="welcome-header welcome-header-v4">
        <span className="welcome-mark" aria-label="Music workspace"><BrandMark size={26} /></span>
      </header>
      <section className="welcome-hero welcome-hero-v4">
        <h1>Listen closer.</h1>
        <p>Bring in a recording. Move between waveform, piano roll, notation, and analysis without losing your place.</p>
        <button className="btn btn-primary" onClick={signIn}>Continue with Google</button>
        <small>Your recordings stay private to your account.</small>
      </section>
    </main>
  );
}
