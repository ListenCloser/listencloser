"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";
import {
  createProject,
  getEntities,
  getInsights,
  getJob,
  getWorkBundle,
  listProjects,
  listWorks,
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
type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

const pause = (milliseconds: number) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds));

async function waitForJob(
  jobId: string,
  onUpdate: (job: JobStatus) => void,
): Promise<JobStatus> {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const job = await getJob(jobId);
    onUpdate(job);
    if (job.stage === "succeeded") return job;
    if (job.stage === "failed" || job.stage === "cancelled") {
      throw new Error(job.error || job.message || `${job.capability} failed`);
    }
    await pause(2000);
  }
  throw new Error("Processing timed out. The job may still be running.");
}

function HomeContent({ onProjectName }: { onProjectName: (name: string) => void }) {
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadWork = useCallback(async (workId: string) => {
    setLoadingWork(true);
    setError(null);
    try {
      let bundle = await getWorkBundle(workId);
      const activeJob = bundle.jobs.find((job) =>
        ["queued", "claimed", "running"].includes(job.lifecycle.current),
      );
      if (activeJob) {
        setFilename(bundle.work.title);
        setStage("processing");
        setProgress(Math.round(activeJob.lifecycle.progress * 100));
        setMessage(activeJob.lifecycle.message || "Understanding music");
        await waitForJob(activeJob.id, (current) => {
          setMessage(current.message || "Understanding music");
          setProgress(Math.round(current.progress * 100));
        });
        bundle = await getWorkBundle(workId);
      }
      const failedJob = bundle.jobs.find(
        (job) => job.lifecycle.current === "failed",
      );
      const hasTranscription = bundle.artifacts.some((item) =>
        ["midi_performance", "midi_corrected"].includes(item.artifact.kind),
      );
      if (failedJob && !hasTranscription) {
        throw new Error(
          failedJob.error || failedJob.lifecycle.message || "Understanding audio failed",
        );
      }
      const latestByKind = new Map(
        bundle.artifacts
          .filter((item) => item.latest_version && item.signed_url)
          .map((item) => [item.artifact.kind, item]),
      );
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
        representations.push({
          kind: "score",
          label: "Score",
          sourceUrl: score.signed_url,
          sourceLabel: "Generated from MIDI",
          confidence: null,
          provenance: "music21 notation",
          musicxml: await response.text(),
          versionId: score.latest_version?.id,
        });
      }

      replaceSources(sources, rendered?.latest_version?.id ?? original?.latest_version?.id);
      replaceRepresentations(representations);
      setStage("success");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load this work");
      setStage("error");
    } finally {
      setLoadingWork(false);
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
    if (!projectId) return;
    setFilename(file.name);
    setStage("uploading");
    setProgress(2);
    setError(null);
    try {
      const { artifact, version } = await uploadArtifact(projectId, file);
      setStage("processing");
      const { job } = await startUnderstandWorkflow(version.id, projectId);
      await waitForJob(job.id, (current) => {
        setMessage(current.message || "Understanding music");
        setProgress(5 + Math.round(current.progress * 90));
      });
      const works = await listWorks(projectId);
      setWorks(works);
      setProgress(100);
      setActiveWorkId(artifact.work_id);
      if (workspace.activeWorkId === artifact.work_id) {
        await loadWork(artifact.work_id);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Import failed");
      setStage("error");
    }
  }, [loadWork, projectId, setActiveWorkId, setWorks, workspace.activeWorkId]);

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
            {!loading && user && projectId && stage === "idle" && !workspace.isLoadingWork && (
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
            {workspace.isLoadingWork && stage !== "processing" && (
              <div className="drop-zone"><strong>Loading persisted work…</strong></div>
            )}
            {(stage === "uploading" || stage === "processing") && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)" }}>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-sm)" }}>{filename}</span>
                <progress value={progress} max={100} style={{ width: "100%" }} />
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>{stage === "uploading" ? "Uploading" : message} · {progress}%</span>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>You can close this page; processing will continue on the server.</span>
              </div>
            )}
            {stage === "error" && (
              <div style={{ background: "var(--danger-soft)", border: "1px solid var(--danger)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)", color: "var(--danger)" }}>
                <strong>Operation failed</strong><span>{error}</span>
                <button className="btn" onClick={() => { setStage("idle"); setError(null); setProgress(0); }}>
                  {workspace.representations.length ? "Dismiss" : "Try another file"}
                </button>
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
  return (
    <WorkspaceShell signedIn={Boolean(user)} projectName={projectName}>
      <HomeContent onProjectName={setProjectName} />
    </WorkspaceShell>
  );
}
