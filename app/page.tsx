"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

const ACCEPT = ".wav,.mp3,.m4a,audio/wav,audio/mp3,audio/mp4,audio/x-m4a";

function generateMockNotes(): { pitch: number; start: number; end: number; velocity: number }[] {
  const scale = [60, 62, 64, 65, 67, 69, 71, 72];
  return Array.from({ length: 42 }, (_, i) => ({
    pitch: scale[i % scale.length],
    start: i * 0.25,
    end: i * 0.25 + 0.22,
    velocity: 80 + Math.floor(Math.random() * 40),
  }));
}

type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

function HomeContent({ onProjectName }: { onProjectName: (name: string) => void }) {
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { addRepresentation } = useWorkspace();
  const { setActiveSource } = useTransport();
  const { setBpm } = useTimeline();

  useEffect(() => {
    onProjectName("My First Project");
  }, [onProjectName]);

  const handleFile = useCallback(
    async (file: File) => {
      setFilename(file.name);
      setStage("uploading");
      setError(null);

      try {
        const audioUrl = URL.createObjectURL(file);
        const name = file.name.replace(/\.[^.]+$/, "");

        await new Promise((r) => setTimeout(r, 600));
        setStage("processing");

        const apiResult = await fetch("/api/v1/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        }).then((r) => r.json()).catch(() => null);

        if (apiResult) {
          onProjectName(apiResult.name);
          await fetch(`/api/v1/projects/${apiResult.id}/artifacts/upload`, {
            method: "POST",
            body: (() => { const fd = new FormData(); fd.append("file", file); return fd; })(),
          }).catch(() => {});
        }

        await new Promise((r) => setTimeout(r, 1000));

        setActiveSource({ id: "uploaded-audio", label: file.name, url: audioUrl, kind: "audio" });
        setBpm(120);

        const notes = generateMockNotes();
        addRepresentation({ kind: "piano_roll", label: "Piano Roll", sourceUrl: "#", sourceLabel: file.name, confidence: null, provenance: "upload", notes });
        addRepresentation({ kind: "waveform", label: "Waveform", sourceUrl: audioUrl, sourceLabel: file.name, confidence: null, provenance: "upload" });
        addRepresentation({ kind: "score", label: "Score", sourceUrl: "#", sourceLabel: "Generated", confidence: 0.8, provenance: "transcription" });
        addRepresentation({ kind: "harmony", label: "Harmony", sourceUrl: "#", sourceLabel: "Key: C major, 120 BPM", confidence: 0.8, provenance: "analysis" });

        setStage("success");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        setStage("error");
      }
    },
    [setBpm, setActiveSource, addRepresentation, onProjectName],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      e.target.value = "";
    },
    [handleFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleRetry = useCallback(() => {
    setStage("idle");
    setFilename("");
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      if (stage === "uploading" || stage === "processing") {
        setStage("idle");
      }
    };
  }, [stage]);

  const showOverlay = stage !== "success";

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
          <div style={{ pointerEvents: "auto", maxWidth: 480, width: "100%", padding: "0 var(--s-4)" }}>
            {stage === "idle" && (
              <div
                className={`drop-zone${dragOver ? " drag-over" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
                onDrop={handleDrop}
              >
                <div style={{ fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>
                  Drop an audio file to start
                </div>
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
                  WAV &middot; MP3 &middot; M4A
                </div>
              </div>
            )}

            {(stage === "uploading" || stage === "processing") && (
              <div style={{
                background: "var(--panel)", border: "1px solid var(--border)",
                borderRadius: "var(--r-lg)", padding: "var(--s-5)",
                display: "flex", flexDirection: "column", gap: "var(--s-4)",
              }}>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{filename}</div>
                <div style={{ height: 6, background: "var(--panel-3)", borderRadius: "var(--r-full)", overflow: "hidden" }}>
                  <div className="pulse" style={{
                    height: "100%", width: stage === "uploading" ? "30%" : "70%",
                    background: "var(--grad-accent-2)", borderRadius: "var(--r-full)",
                    transition: "width 0.3s var(--ease)",
                  }} />
                </div>
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
                  {stage === "uploading" ? "Uploading file..." : "Processing audio..."}
                </div>
              </div>
            )}

            {stage === "error" && (
              <div style={{
                background: "var(--panel)", border: "1px solid var(--danger)",
                borderRadius: "var(--r-lg)", padding: "var(--s-5)",
                display: "flex", flexDirection: "column", gap: "var(--s-4)", textAlign: "center",
              }}>
                <div style={{ fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--danger)" }}>
                  Processing Failed
                </div>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{error}</div>
                <button className="btn btn-primary" onClick={handleRetry}>Try Again</button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default function Home() {
  const [projectName, setProjectName] = useState("hello-ai");
  return (
    <WorkspaceShell projectName={projectName}>
      <HomeContent onProjectName={setProjectName} />
    </WorkspaceShell>
  );
}
