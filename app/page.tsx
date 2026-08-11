"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import WorkspaceShell, { type ServiceStatus } from "@/components/workspace/WorkspaceShell";
import {
  cancelJob,
  createProject,
  getEntities,
  getInsights,
  getJob,
  getWorkBundle,
  listProjects,
  listWorks,
  retryJob,
  startUnderstandWorkflow,
  uploadArtifact,
} from "@/lib/api-client";
import type { JobStatus } from "@/lib/domain.types";
import { supabase } from "@/lib/supabase";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import {
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

const ACCEPT = ".wav,.mp3,.m4a,.flac,.ogg,.aac,audio/*";
const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(["wav", "mp3", "m4a", "flac", "ogg", "aac"]);
type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

const pause = (milliseconds: number) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds));

class JobTerminalError extends Error {
  constructor(
    message: string,
    readonly stage: "failed" | "cancelled",
  ) {
    super(message);
  }
}

async function waitForJob(
  jobId: string,
  onUpdate: (job: JobStatus) => void,
): Promise<JobStatus> {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const job = await getJob(jobId);
    onUpdate(job);
    if (job.stage === "succeeded") return job;
    if (job.stage === "failed" || job.stage === "cancelled") {
      throw new JobTerminalError(
        job.error || job.message || `${job.capability} ${job.stage}`,
        job.stage,
      );
    }
    await pause(2000);
  }
  throw new Error("Processing timed out. The job may still be running.");
}

function HomeContent({ onProjectName, serviceStatus, refreshService }: { onProjectName: (name: string) => void; serviceStatus: ServiceStatus; refreshService: () => void }) {
  const { user, loading } = useAuth();
  const {
    replaceRepresentations,
    setActiveWorkId,
    setInsights,
    setLoadingWork,
    setProject,
    setWorks,
    workspace,
  } = useWorkspace();
  const { replaceSources } = useTransport();
  const { setBpm, setTimeSignature } = useTimeline();
  const [projectId, setProjectId] = useState("");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [processingWorkId, setProcessingWorkId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadSequenceRef = useRef(0);

  const loadWork = useCallback(async (workId: string) => {
    const sequence = ++loadSequenceRef.current;
    setLoadingWork(true);
    setError(null);
    try {
      let bundle = await getWorkBundle(workId);
      if (sequence !== loadSequenceRef.current) return;
      let latestJob = bundle.jobs[0];
      const activeJob = latestJob &&
        ["queued", "claimed", "running"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;
      if (activeJob) {
        setActiveJobId(activeJob.id);
        setFilename(bundle.work.title);
        setStage("processing");
        setProgress(Math.round(activeJob.lifecycle.progress * 100));
        setMessage(activeJob.lifecycle.message || "Understanding music");
        try {
          await waitForJob(activeJob.id, (current) => {
            if (sequence !== loadSequenceRef.current) return;
            setMessage(current.message || "Understanding music");
            setProgress(Math.round(current.progress * 100));
          });
        } catch (cause) {
          // Terminal jobs can still have useful partial artifacts. Re-fetch the
          // bundle and render those before presenting retry controls.
          if (!(cause instanceof JobTerminalError)) throw cause;
        }
        bundle = await getWorkBundle(workId);
        if (sequence !== loadSequenceRef.current) return;
        latestJob = bundle.jobs[0];
        setActiveJobId(null);
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
      const rendered = latestByKind.get("audio_rendered");
      const midi = latestByKind.get("midi_performance") ?? latestByKind.get("midi_corrected");
      const score = latestByKind.get("musicxml_score");

      const sources: PlaybackSource[] = [];
      if (original?.latest_version && original.signed_url) {
        sources.push({
          id: original.latest_version.id,
          label: "Original audio",
          url: original.signed_url,
          kind: "audio",
        });
      }
      if (rendered?.latest_version && rendered.signed_url) {
        sources.push({
          id: rendered.latest_version.id,
          label: "Transcription playback",
          url: rendered.signed_url,
          kind: "audio",
        });
      }

      const representations: RepresentationEntry[] = [];
      if (original?.signed_url) {
        representations.push({
          kind: "waveform",
          label: "Waveform",
          sourceUrl: original.signed_url,
          sourceLabel: "Original audio",
          confidence: null,
          provenance: "uploaded source",
          audioUrl: original.signed_url,
          versionId: original.latest_version?.id,
        });
      }

      if (midi?.latest_version) {
        const [entities, insights] = await Promise.all([
          getEntities(midi.latest_version.id),
          getInsights(midi.latest_version.id),
        ]);
        if (sequence !== loadSequenceRef.current) return;
        const notes = entities.flatMap((entity) => entity.note ? [{
          pitch: entity.note.pitch,
          start: entity.note.start_seconds,
          end: entity.note.end_seconds,
          velocity: entity.note.velocity,
        }] : []);
        representations.push({
          kind: "piano_roll",
          label: "Piano Roll",
          sourceUrl: midi.signed_url ?? "",
          sourceLabel: `${notes.length} detected notes`,
          confidence: null,
          provenance: "basic-pitch transcription",
          notes,
          versionId: midi.latest_version.id,
        });
        setInsights(insights);
        const tempo = insights.find((item) => item.kind === "tempo")?.evidence.bpm;
        if (typeof tempo === "number" && tempo > 0) setBpm(tempo);
        const signature = insights.find((item) => item.kind === "time_signature")?.evidence;
        if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
          setTimeSignature(signature.numerator, signature.denominator);
        }
      } else {
        setInsights([]);
      }

      if (score?.signed_url) {
        const response = await fetch(score.signed_url);
        if (!response.ok) throw new Error("Could not load the persisted MusicXML score");
        const musicxml = await response.text();
        if (sequence !== loadSequenceRef.current) return;
        representations.push({
          kind: "score",
          label: "Score",
          sourceUrl: score.signed_url,
          sourceLabel: "Generated from MIDI",
          confidence: null,
          provenance: "music21 notation",
          musicxml,
          versionId: score.latest_version?.id,
        });
      }

      replaceSources(sources, rendered?.latest_version?.id ?? original?.latest_version?.id);
      replaceRepresentations(representations);
      if (terminalJob) {
        setActiveJobId(terminalJob.id);
        setError(
          terminalJob.error ||
            terminalJob.lifecycle.message ||
            `Understanding audio ${terminalJob.lifecycle.current}`,
        );
        setStage("error");
      } else if (representations.length === 0) {
        setError("This work has no playable artifacts yet. Import the source audio again.");
        setStage("error");
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
  }, [replaceRepresentations, replaceSources, setBpm, setInsights, setLoadingWork, setTimeSignature]);

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
    setStage("uploading");
    setProgress(2);
    setError(null);
    try {
      const { artifact, version } = await uploadArtifact(projectId, file);
      setProcessingWorkId(artifact.work_id);
      setWorks(await listWorks(projectId));
      setStage("processing");
      const { job } = await startUnderstandWorkflow(version.id, projectId);
      setActiveJobId(job.id);
      await waitForJob(job.id, (current) => {
        setMessage(current.message || "Understanding music");
        setProgress(5 + Math.round(current.progress * 90));
      });
      const works = await listWorks(projectId);
      setWorks(works);
      setProgress(100);
      setActiveJobId(null);
      setActiveWorkId(artifact.work_id);
      setProcessingWorkId(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Import failed");
      setStage("error");
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
        setMessage(current.message || "Retrying music understanding");
        setProgress(Math.round(current.progress * 100));
      });
      setActiveJobId(null);
      if (workspace.activeWorkId === workId) await loadWork(workId);
      else setActiveWorkId(workId);
      setProcessingWorkId(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Retry failed");
      setStage("error");
    }
  }, [activeJobId, loadWork, processingWorkId, setActiveWorkId, workspace.activeWorkId]);

  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  const showOverlay =
    workspace.representations.length === 0 ||
    stage === "processing" ||
    stage === "uploading" ||
    stage === "error";

  return (
    <>
      <input
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
            {!loading && !user && (
              <div className="drop-zone">
                <strong>Sign in to start a music session</strong>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>Your source files and generated artifacts remain private.</span>
                <button className="btn btn-primary" onClick={signIn}>Sign in with Google</button>
              </div>
            )}
            {!loading && user && projectId && serviceStatus === "ready" && stage === "idle" && !workspace.isLoadingWork && (
              <div
                className={`drop-zone${dragOver ? " drag-over" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragOver(false);
                  const file = event.dataTransfer.files[0];
                  if (file) void handleFile(file);
                }}
              >
                <strong>Drop an audio file to understand it</strong>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>WAV · MP3 · M4A · FLAC · OGG · AAC</span>
              </div>
            )}
            {!loading && user && serviceStatus === "checking" && stage === "idle" && (
              <div className="drop-zone"><strong>Checking the processing service…</strong><span>Imports will be enabled when it is ready.</span></div>
            )}
            {!loading && user && serviceStatus === "unavailable" && stage === "idle" && (
              <div className="service-unavailable" role="alert">
                <span className="service-kicker">Service interruption</span>
                <strong>Audio processing is temporarily offline</strong>
                <span>Your existing work is safe. Retry the connection before importing a new file.</span>
                <button type="button" className="btn btn-primary" onClick={refreshService}>Check again</button>
              </div>
            )}
            {workspace.isLoadingWork && stage !== "processing" && (
              <div className="drop-zone"><strong>Loading persisted work…</strong></div>
            )}
            {(stage === "uploading" || stage === "processing") && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)" }}>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-sm)" }}>{filename}</span>
                <progress value={progress} max={100} style={{ width: "100%" }} />
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>{stage === "uploading" ? "Uploading" : message} · {progress}%</span>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>You can close this page; processing will continue on the server.</span>
                {stage === "processing" && activeJobId && (
                  <button className="btn" onClick={() => void cancelActiveJob()}>
                    Cancel processing
                  </button>
                )}
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
                  <button className="btn" onClick={() => { setStage("idle"); setError(null); setProgress(0); }}>
                    {workspace.representations.length ? "Dismiss" : "Try another file"}
                  </button>
                </div>
              </div>
            )}
          </div>
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
  return (
    <WorkspaceShell signedIn={Boolean(user)} projectName={projectName} serviceStatus={serviceStatus}>
      <HomeContent onProjectName={setProjectName} serviceStatus={serviceStatus} refreshService={refreshService} />
    </WorkspaceShell>
  );
}
