"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import {
  createProject,
  uploadArtifact,
  startUnderstandWorkflow,
  getJob,
} from "@/lib/api-client";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

const ACCEPT = ".wav,.mp3,.m4a,audio/wav,audio/mp3,audio/mp4,audio/x-m4a";

type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

function HomeContent({ onProjectName }: { onProjectName: (name: string) => void }) {
  const [projectId, setProjectId] = useState("");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobMessage, setJobMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioUrlRef = useRef<string | null>(null);

  const { addRepresentation, workspace } = useWorkspace();
  const { setActiveSource } = useTransport();
  const { setBpm } = useTimeline();

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const p = await createProject("My First Project");
        if (cancelled) return;
        setProjectId(p.id);
        onProjectName(p.name);
      } catch {
        if (!cancelled) onProjectName("hello-ai");
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [onProjectName]);

  const handleFile = useCallback(
    async (file: File) => {
      if (!projectId) return;
      setFilename(file.name);
      setStage("uploading");
      setError(null);
      try {
        const { version } = await uploadArtifact(projectId, file);
        audioUrlRef.current = URL.createObjectURL(file);
        setStage("processing");
        setJobProgress(0);
        setJobMessage("Starting transcription...");
        const { job } = await startUnderstandWorkflow(version.id, projectId);
        setJobId(job.id);
        setJobProgress(job.lifecycle.progress);
        setJobMessage(job.lifecycle.message);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        setStage("error");
      }
    },
    [projectId],
  );

  useEffect(() => {
    if (stage !== "processing" || !jobId || !projectId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const job = await getJob(jobId);
        if (cancelled) return;
        setJobProgress(job.lifecycle.progress);
        setJobMessage(job.lifecycle.message);
        if (job.lifecycle.current === "succeeded") {
          const meta = job.provenance as Record<string, unknown> | undefined;
          const bpm = (meta?.metadata as Record<string, unknown> | undefined)?.bpm;
          if (typeof bpm === "number") setBpm(bpm);
          if (audioUrlRef.current) {
            setActiveSource({
              id: "uploaded-audio",
              label: filename,
              url: audioUrlRef.current,
              kind: "audio",
            });
          }
          addRepresentation({
            kind: "piano_roll",
            label: "Piano Roll",
            sourceUrl: "#",
            sourceLabel: filename,
            confidence: null,
            provenance: "project",
          });
          addRepresentation({
            kind: "waveform",
            label: "Waveform",
            sourceUrl: "#",
            sourceLabel: filename,
            confidence: null,
            provenance: "project",
          });
          addRepresentation({ kind: "score", label: "Score", sourceUrl: "#", sourceLabel: "Generated", confidence: 0.8, provenance: "transcription" });
          addRepresentation({ kind: "harmony", label: "Harmony", sourceUrl: "#", sourceLabel: "Key: C major, 120 BPM", confidence: 0.8, provenance: "analysis" });
          setStage("success");
          return;
        }
        if (job.lifecycle.current === "failed") {
          setError(job.lifecycle.message || job.error || "Job failed");
          setStage("error");
          return;
        }
        setTimeout(poll, 2000);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Polling failed");
          setStage("error");
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [stage, jobId, projectId, filename, setBpm, setActiveSource, addRepresentation]);

  useEffect(() => {
    return () => {
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleRetry = useCallback(() => {
    setStage("idle");
    setError(null);
    setJobId(null);
    setJobProgress(0);
    setJobMessage("");
    setFilename("");
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const showOverlay = workspace.representations.length === 0 && projectId !== "";

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      {showOverlay && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 50,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              pointerEvents: "auto",
              maxWidth: 480,
              width: "100%",
              padding: "0 var(--s-4)",
            }}
          >
            {stage === "idle" && (
              <div
                className={`drop-zone${dragOver ? " drag-over" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                }}
                onDrop={handleDrop}
              >
                <div
                  style={{
                    fontSize: "var(--fs-md)",
                    fontWeight: "var(--fw-semibold)",
                    color: "var(--text)",
                  }}
                >
                  Drop an audio file to start
                </div>
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
                  WAV &middot; MP3 &middot; M4A
                </div>
              </div>
            )}

            {(stage === "uploading" || stage === "processing") && (
              <div
                style={{
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r-lg)",
                  padding: "var(--s-5)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--s-4)",
                }}
              >
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>
                  {filename}
                </div>
                <div
                  style={{
                    height: 6,
                    background: "var(--panel-3)",
                    borderRadius: "var(--r-full)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${jobProgress}%`,
                      background: "var(--accent)",
                      borderRadius: "var(--r-full)",
                      transition: "width 0.3s var(--ease)",
                    }}
                  />
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "var(--fs-xs)",
                    color: "var(--muted)",
                  }}
                >
                  <span>
                    {stage === "uploading"
                      ? "Uploading..."
                      : jobMessage || "Processing..."}
                  </span>
                  <span>{jobProgress}%</span>
                </div>
              </div>
            )}

            {stage === "error" && (
              <div
                style={{
                  background: "var(--danger-soft)",
                  border: "1px solid var(--danger)",
                  borderRadius: "var(--r-lg)",
                  padding: "var(--s-5)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--s-3)",
                  color: "var(--danger)",
                  fontSize: "var(--fs-sm)",
                }}
              >
                <div style={{ fontWeight: "var(--fw-semibold)" }}>Import failed</div>
                <div>{error}</div>
                <button
                  onClick={handleRetry}
                  style={{
                    alignSelf: "flex-start",
                    padding: "var(--s-2) var(--s-4)",
                    background: "var(--danger)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "var(--r-md)",
                    fontSize: "var(--fs-xs)",
                    fontWeight: "var(--fw-medium)",
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  Retry
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
  const [projectName, setProjectName] = useState("");

  return (
    <WorkspaceShell projectName={projectName}>
      <HomeContent onProjectName={setProjectName} />
    </WorkspaceShell>
  );
}
