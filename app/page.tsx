"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

const ACCEPT = ".wav,.mp3,.m4a,audio/wav,audio/mp3,audio/mp4,audio/x-m4a";

type Note = { pitch: number; start: number; end: number; velocity: number };

async function apiPost(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiUpload(path: string, file: File, extra: Record<string, string>): Promise<unknown> {
  const fd = new FormData();
  fd.append("file", file);
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  const res = await fetch(path, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
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

  useEffect(() => { onProjectName("hello-ai"); }, [onProjectName]);

  const handleFile = useCallback(async (file: File) => {
    setFilename(file.name);
    setStage("uploading");
    setError(null);

    try {
      const audioUrl = URL.createObjectURL(file);
      const name = file.name.replace(/\.[^.]+$/, "");
      let notes: Note[] = [];
      let useRealPipeline = true;

      if (useRealPipeline) {
        try {
          const proj = await apiPost("/api/v1/projects", { name }) as { id: string; name: string };
          onProjectName(proj.name);
          const work = await apiPost(`/api/v1/projects/${proj.id}/works`, { title: name }) as { id: string };
          const uploadResult = await apiUpload(
            `/api/v1/projects/${proj.id}/artifacts/upload`, file, { work_id: work.id }
          ) as { version: { id: string } };
          const vid = uploadResult.version?.id;
          if (!vid || vid === "mock-version-1") throw new Error("Upload returned invalid version");

          setStage("processing");

          const transcribeResult = await apiPost(
            `/api/v1/versions/${vid}/transcribe`, {}
          ) as { notes: Note[]; num_notes: number; midi_version_id: string };

          notes = transcribeResult.notes;
          if (notes.length > 0 && notes[0].velocity === undefined) {
            notes = []; useRealPipeline = false;
          }

          let bpmDetected = 120;
          let keyLabel = "C major";
          try {
            const analyzeResult = await apiPost(
              `/api/v1/versions/${transcribeResult.midi_version_id}/analyze`, {}
            ) as { analysis: { tempo: { bpm: number }; key: { tonic: string; mode: string } } };
            if (analyzeResult.analysis?.tempo?.bpm) {
              bpmDetected = Math.round(analyzeResult.analysis.tempo.bpm);
            }
            if (analyzeResult.analysis?.key?.tonic && analyzeResult.analysis?.key?.mode) {
              keyLabel = `${analyzeResult.analysis.key.tonic} ${analyzeResult.analysis.key.mode}`;
            }
          } catch {
            // analysis is optional — continue with defaults
          }

          setActiveSource({ id: "uploaded-audio", label: file.name, url: audioUrl, kind: "audio" });
          setBpm(bpmDetected);

          addRepresentation({ kind: "piano_roll", label: "Piano Roll", sourceUrl: "#", sourceLabel: file.name, confidence: 0.85, provenance: "transcription", notes });
          addRepresentation({ kind: "waveform", label: "Waveform", sourceUrl: audioUrl, sourceLabel: file.name, confidence: null, provenance: "upload" });
          addRepresentation({ kind: "score", label: "Score", sourceUrl: "#", sourceLabel: "Generated", confidence: 0.8, provenance: "transcription" });
          addRepresentation({ kind: "harmony", label: "Harmony", sourceUrl: "#", sourceLabel: `Key: ${keyLabel}, ${bpmDetected} BPM`, confidence: 0.8, provenance: "analysis" });

          setStage("success");
          return;
        } catch {
          useRealPipeline = false;
        }
      }

      setStage("processing");
      await new Promise((r) => setTimeout(r, 1000));
      setActiveSource({ id: "uploaded-audio", label: file.name, url: audioUrl, kind: "audio" });
      setBpm(120);

      addRepresentation({ kind: "piano_roll", label: "Piano Roll", sourceUrl: "#", sourceLabel: file.name, confidence: null, provenance: "upload", notes });
      addRepresentation({ kind: "waveform", label: "Waveform", sourceUrl: audioUrl, sourceLabel: file.name, confidence: null, provenance: "upload" });

      setStage("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStage("error");
    }
  }, [setBpm, setActiveSource, addRepresentation, onProjectName]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }, [handleFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const showOverlay = stage !== "success";

  return (
    <>
      <input ref={fileInputRef} type="file" accept={ACCEPT} style={{ display: "none" }} onChange={handleFileChange} />
      {showOverlay && (
        <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, pointerEvents: "none" }}>
          <div style={{ pointerEvents: "auto", maxWidth: 480, width: "100%", padding: "0 var(--s-4)" }}>
            {stage === "idle" && (
              <div className={`drop-zone${dragOver ? " drag-over" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
                onDrop={handleDrop}>
                <div style={{ fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>Drop an audio file to start</div>
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>WAV &middot; MP3 &middot; M4A</div>
              </div>
            )}
            {(stage === "uploading" || stage === "processing") && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "flex", flexDirection: "column", gap: "var(--s-4)" }}>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{filename}</div>
                <div style={{ height: 6, background: "var(--panel-3)", borderRadius: "var(--r-full)", overflow: "hidden" }}>
                  <div className="pulse" style={{ height: "100%", width: stage === "uploading" ? "30%" : "70%", background: "var(--grad-accent-2)", borderRadius: "var(--r-full)", transition: "width 0.3s var(--ease)" }} />
                </div>
                <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>{stage === "uploading" ? "Uploading file..." : "Processing audio..."}</div>
              </div>
            )}
            {stage === "error" && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--danger)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "flex", flexDirection: "column", gap: "var(--s-4)", textAlign: "center" }}>
                <div style={{ fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--danger)" }}>Processing Failed</div>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{error}</div>
                <button className="btn btn-primary" onClick={() => { setStage("idle"); setFilename(""); setError(null); }}>Try Again</button>
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
