"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { supabase } from "@/lib/supabase";
import type { Entity } from "@/lib/domain.types";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

const ACCEPT = ".wav,.mp3,.m4a,audio/wav,audio/mp3,audio/mp4,audio/x-m4a";

type Note = { pitch: number; start: number; end: number; velocity: number };

async function apiPost(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function apiUpload(path: string, file: File, extra: Record<string, string>): Promise<unknown> {
  const fd = new FormData();
  fd.append("file", file);
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  const res = await fetch(path, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

function HomeContent({ onProjectName, onVersion }: { onProjectName: (name: string) => void; onVersion: (id: string, label: string, entities: Entity[]) => void }) {
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [processingMsg, setProcessingMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addRepresentation, setMidiVersionId } = useWorkspace();
  const { setActiveSource } = useTransport();
  const { setBpm } = useTimeline();

  useEffect(() => { onProjectName("hello-ai"); }, [onProjectName]);

  const handleFile = useCallback(async (file: File) => {
    setFilename(file.name);
    setStage("uploading");
    setProcessingMsg("Uploading...");
    setError(null);

    try {
      const audioUrl = URL.createObjectURL(file);
      const name = file.name.replace(/\.[^.]+$/, "");

      setProcessingMsg("Creating project...");
      const proj = await apiPost("/api/v1/projects", { name }) as { id: string; name: string };
      onProjectName(proj.name);

      setProcessingMsg("Uploading file...");
      const work = await apiPost(`/api/v1/projects/${proj.id}/works`, { title: name }) as { id: string };
      const uploadResult = await apiUpload(`/api/v1/projects/${proj.id}/artifacts/upload`, file, { work_id: work.id }) as { version: { id: string } };
      const vid = uploadResult.version?.id;
      if (!vid) throw new Error("Upload failed");

      setStage("processing");
      setProcessingMsg("Transcribing audio... (this may take a minute)");

      const transcribeResult = await apiPost(`/api/v1/versions/${vid}/transcribe`, {}) as { notes: Note[]; midi_version_id: string };
      const notes = transcribeResult.notes || [];
      const midiVid = transcribeResult.midi_version_id;
      if (midiVid) setMidiVersionId(midiVid);

      let keyLabel = "C major";
      let bpmVal = 120;
      try {
        const ar = await apiPost(`/api/v1/versions/${midiVid}/analyze`, {}) as { analysis: { tempo: { bpm: number }; key: { tonic: string; mode: string } } };
        if (ar.analysis?.tempo?.bpm) bpmVal = Math.round(ar.analysis.tempo.bpm);
        if (ar.analysis?.key) keyLabel = `${ar.analysis.key.tonic} ${ar.analysis.key.mode}`;
      } catch { /* optional */ }

      setActiveSource({ id: "source", label: file.name, url: audioUrl, kind: "audio" });
      setBpm(bpmVal);

      addRepresentation({ kind: "piano_roll", label: "Piano Roll", sourceUrl: "#", sourceLabel: `${notes.length} notes`, confidence: 0.85, provenance: "transcription", notes });
      addRepresentation({ kind: "waveform", label: "Waveform", sourceUrl: audioUrl, sourceLabel: file.name, confidence: null, provenance: "upload" });
      if (midiVid) addRepresentation({ kind: "score", label: "Score", sourceUrl: `/api/v1/versions/${midiVid}/musicxml`, sourceLabel: "Sheet Music", confidence: 0.8, provenance: "transcription" });
      addRepresentation({ kind: "harmony", label: "Harmony", sourceUrl: "#", sourceLabel: `Key: ${keyLabel}, ${bpmVal} BPM`, confidence: 0.8, provenance: "analysis" });

      try {
        const entities = await fetch(`/api/v1/versions/${vid}/entities`).then(r => r.json());
        onVersion(vid, `${notes.length} notes`, Array.isArray(entities) ? entities : []);
        if (midiVid) {
          const midiEntities = await fetch(`/api/v1/versions/${midiVid}/entities`).then(r => r.json());
          onVersion(midiVid, "MIDI", Array.isArray(midiEntities) ? midiEntities : []);
        }
      } catch { /* entities for compare are optional */ }

      setStage("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setStage("error");
    }
  }, [setBpm, setActiveSource, addRepresentation, onProjectName, onVersion]);

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

  if (stage === "idle" || stage === "error") {
    return (
      <>
        <input ref={fileInputRef} type="file" accept={ACCEPT} style={{ display: "none" }} onChange={handleFileChange} />
        <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, pointerEvents: "none", background: "rgba(10,10,15,0.85)" }}>
          <div style={{ pointerEvents: "auto", maxWidth: 440, width: "100%", padding: "0 var(--s-4)" }}>
            {stage === "idle" && (
              <div className={`drop-zone${dragOver ? " drag-over" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
                onDrop={handleDrop}>
                <div style={{ fontSize: "var(--fs-lg)", fontWeight: "var(--fw-semibold)", marginBottom: "var(--s-2)" }}>Drop an audio file</div>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>WAV &middot; MP3 &middot; M4A &middot; FLAC</div>
              </div>
            )}
            {stage === "error" && (
              <div style={{ background: "var(--panel)", border: "1px solid var(--danger)", borderRadius: "var(--r-lg)", padding: "var(--s-5)", display: "flex", flexDirection: "column", gap: "var(--s-3)", textAlign: "center" }}>
                <div style={{ fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--danger)" }}>Something went wrong</div>
                <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{error}</div>
                <button className="btn btn-primary" onClick={() => { setStage("idle"); setFilename(""); setError(null); }}>Try again</button>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <input ref={fileInputRef} type="file" accept={ACCEPT} style={{ display: "none" }} onChange={handleFileChange} />
      {(stage === "uploading" || stage === "processing") && (
        <div style={{ padding: "var(--s-2) var(--s-4)", background: "var(--panel-2)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "var(--s-3)", fontSize: "var(--fs-sm)" }}>
          <div className="spinner" style={{ width: 14, height: 14 }} />
          <span style={{ color: "var(--muted)" }}>{processingMsg}</span>
          <span style={{ color: "var(--text)", fontWeight: "var(--fw-medium)" }}>{filename}</span>
        </div>
      )}
    </>
  );
}

export default function Home() {
  const [projectName, setProjectName] = useState("hello-ai");
  const [versions, setVersions] = useState<Array<{ id: string; label: string; entities: Entity[] }>>([]);

  const addVersion = useCallback((id: string, label: string, entities: Entity[]) => {
    setVersions((prev) => {
      if (prev.some((v) => v.id === id)) return prev;
      return [...prev, { id, label, entities }];
    });
  }, []);

  const handleSignOut = useCallback(() => { supabase?.auth.signOut(); window.location.reload(); }, []);
  const handleSignIn = useCallback(async () => {
    if (!supabase) return;
    await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent("/")}` } });
  }, []);

  return (
    <WorkspaceShell projectName={projectName} versions={versions} onSignIn={handleSignIn} onSignOut={handleSignOut}>
      <HomeContent onProjectName={setProjectName} onVersion={addVersion} />
    </WorkspaceShell>
  );
}
