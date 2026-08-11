"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";
import {
  createProject,
  getEntities,
  getInsights,
  getJob,
  getVersionResource,
  listProjects,
  startAnalyzeWorkflow,
  startCreateWorkflow,
  startUnderstandWorkflow,
  uploadArtifact,
} from "@/lib/api-client";
import type { JobStatus } from "@/lib/domain.types";
import { supabase } from "@/lib/supabase";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

const ACCEPT = ".wav,.mp3,.m4a,.flac,.ogg,audio/*";
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
  const { addRepresentation, setInsights, workspace } = useWorkspace();
  const { setActiveSource } = useTransport();
  const { setBpm, setTimeSignature } = useTimeline();
  const [projectId, setProjectId] = useState("");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (loading || !user) {
      setProjectId("");
      return;
    }
    void (async () => {
      try {
        const projects = await listProjects();
        const project = projects.find((item) => !item.archived_at) ??
          await createProject("Music Lab", "Audio transformations and analysis");
        if (!cancelled) {
          setProjectId(project.id);
          onProjectName(project.name);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load a project");
          setStage("error");
        }
      }
    })();
    return () => { cancelled = true; };
  }, [loading, user, onProjectName]);

  const handleFile = useCallback(async (file: File) => {
    if (!projectId) return;
    setFilename(file.name);
    setStage("uploading");
    setProgress(2);
    setError(null);

    try {
      const { version } = await uploadArtifact(projectId, file);
      setStage("processing");
      setMessage("Queued transcription");
      setProgress(5);
      const { job } = await startUnderstandWorkflow(version.id, projectId);
      const transcription = await waitForJob(job.id, (current) => {
        setMessage(current.message || "Transcribing audio");
        setProgress(5 + Math.round(current.progress * 60));
      });

      const resources = await Promise.all(
        transcription.output_version_ids.map(getVersionResource),
      );
      const midi = resources.find((item) => item.artifact.kind === "midi_performance");
      const renderedAudio = resources.find((item) => item.artifact.kind === "audio_rendered");
      if (!midi) throw new Error("Transcription completed without a MIDI result");

      const entities = await getEntities(midi.version.id);
      const notes = entities.flatMap((entity) => entity.note ? [{
        pitch: entity.note.pitch,
        start: entity.note.start_seconds,
        end: entity.note.end_seconds,
        velocity: entity.note.velocity,
      }] : []);
      addRepresentation({
        kind: "piano_roll",
        label: "Piano Roll",
        sourceUrl: midi.signed_url,
        sourceLabel: `${notes.length} detected notes`,
        confidence: null,
        provenance: "basic-pitch transcription",
        notes,
        versionId: midi.version.id,
      });

      if (renderedAudio) {
        setActiveSource({
          id: renderedAudio.version.id,
          label: `${file.name} — transcription playback`,
          url: renderedAudio.signed_url,
          kind: "audio",
        });
        addRepresentation({
          kind: "waveform",
          label: "Waveform",
          sourceUrl: renderedAudio.signed_url,
          sourceLabel: "MIDI render",
          confidence: null,
          provenance: "transcription",
          audioUrl: renderedAudio.signed_url,
          versionId: renderedAudio.version.id,
        });
      }

      setMessage("Analyzing harmony and creating score");
      setProgress(70);
      const [{ job: analysisJob }, { job: scoreJob }] = await Promise.all([
        startAnalyzeWorkflow(midi.version.id, projectId),
        startCreateWorkflow(midi.version.id, projectId, "score"),
      ]);

      const analysisPromise = waitForJob(analysisJob.id, (current) => {
        setMessage(current.message || "Analyzing music");
        setProgress(70 + Math.round(current.progress * 15));
      }).then(async () => {
        const insights = await getInsights(midi.version.id);
        setInsights(insights);
        const tempo = insights.find((item) => item.kind === "tempo")?.evidence.bpm;
        if (typeof tempo === "number" && tempo > 0) setBpm(tempo);
        const signature = insights.find((item) => item.kind === "time_signature")?.evidence;
        if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
          setTimeSignature(signature.numerator, signature.denominator);
        }
      });

      const scorePromise = waitForJob(scoreJob.id, (current) => {
        setMessage(current.message || "Creating score");
        setProgress(85 + Math.round(current.progress * 14));
      }).then(async (result) => {
        const scoreId = result.output_version_ids[0];
        if (!scoreId) return;
        const score = await getVersionResource(scoreId);
        const response = await fetch(score.signed_url);
        if (!response.ok) throw new Error("Could not load generated MusicXML");
        addRepresentation({
          kind: "score",
          label: "Score",
          sourceUrl: score.signed_url,
          sourceLabel: "Generated from MIDI",
          confidence: null,
          provenance: "music21 notation",
          musicxml: await response.text(),
          versionId: score.version.id,
        });
      });

      const derived = await Promise.allSettled([analysisPromise, scorePromise]);
      const failures = derived.filter((item) => item.status === "rejected");
      if (failures.length) {
        const details = failures.map((item) => {
          const reason = (item as PromiseRejectedResult).reason;
          return reason instanceof Error ? reason.message : String(reason);
        });
        setError(`Transcription succeeded, but a derived result failed: ${details.join("; ")}`);
        setProgress(100);
        setStage("error");
        return;
      }
      setProgress(100);
      setMessage("Analysis complete");
      setStage("success");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Import failed");
      setStage("error");
    }
  }, [addRepresentation, projectId, setActiveSource, setBpm, setInsights, setTimeSignature]);

  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  const showOverlay = workspace.representations.length === 0 || stage === "processing" || stage === "error";

  return (
    <>
      <input ref={fileInputRef} type="file" accept={ACCEPT} hidden onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) void handleFile(file);
      }} />
      {showOverlay && (
        <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, pointerEvents: "none" }}>
          <div style={{ pointerEvents: "auto", maxWidth: 480, width: "100%", padding: "var(--s-4)" }}>
            {!loading && !user && (
              <div className="drop-zone">
                <strong>Sign in to start a music session</strong>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>Uploads and generated artifacts are private to your account.</span>
                <button className="btn btn-primary" onClick={signIn}>Sign in with Google</button>
              </div>
            )}
            {!loading && user && projectId && stage === "idle" && (
              <div className={`drop-zone${dragOver ? " drag-over" : ""}`} onClick={() => fileInputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={(event) => { event.preventDefault(); setDragOver(false); const file = event.dataTransfer.files[0]; if (file) void handleFile(file); }}>
                <strong>Drop an audio file to start</strong>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>WAV · MP3 · M4A · FLAC · OGG</span>
              </div>
            )}
            {(stage === "uploading" || stage === "processing") && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)" }}>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-sm)" }}>{filename}</span>
                <progress value={progress} max={100} style={{ width: "100%" }} />
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>{stage === "uploading" ? "Uploading" : message} · {progress}%</span>
              </div>
            )}
            {stage === "error" && (
              <div style={{ background: "var(--danger-soft)", border: "1px solid var(--danger)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "grid", gap: "var(--s-3)", color: "var(--danger)" }}>
                <strong>Import failed</strong><span>{error}</span>
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
