"use client";

import { useEffect, useState, useRef } from "react";
import { isSupabaseConfigured } from "@/lib/supabase";
import {
  uploadToLibrary,
  listLibrary,
  deleteFromLibrary,
  formatTime,
  deriveTrackState,
  type LibFile,
  type Transcription,
} from "@/lib/music";
import Visualizer from "@/components/Visualizer";
import { useSharedAudio } from "@/lib/audio-context";

function formatSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Library({
  signedIn,
  onSignIn,
  onTranscribe,
  onAnalyze,
  onVisualize,
  onTrackDeleted,
  transcriptions,
  refreshKey,
  isTranscribing,
  isAnalyzing,
}: {
  signedIn?: boolean;
  onSignIn?: () => void;
  onTranscribe?: (file: LibFile) => void;
  onAnalyze?: (file: LibFile) => void;
  onVisualize?: (file: LibFile) => void;
  onTrackDeleted?: (id: string) => void;
  transcriptions?: Transcription[];
  refreshKey?: number;
  isTranscribing?: boolean;
  isAnalyzing?: boolean;
}) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<LibFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);
  const [recordTimer, setRecordTimer] = useState(0);

  const { audioRef, playing, paused, currentTime, duration, stop: stopAudio, toggle: togglePlay, pause, resume } = useSharedAudio();

  const dropRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  async function refresh() {
    if (!isSupabaseConfigured) { setLoading(false); return; }
    setLoading(true);
    try {
      setFiles(await listLibrary());
    } catch (e) {
      setStatus("⚠️ " + (e instanceof Error ? e.message : "list failed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (signedIn) refresh();
  }, [signedIn, refreshKey]);

  useEffect(() => {
    return () => {
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
    };
  }, []);

  async function uploadFile(file: File) {
    if (busy) return;
    setBusy(true);
    setStatus("Uploading…");
    try {
      await uploadToLibrary(file.name, file);
      setStatus(`Saved ✓ ${file.name}`);
      await refresh();
    } catch (err) {
      setStatus("⚠️ " + (err instanceof Error ? err.message : "upload failed"));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadFile(file);
    e.target.value = "";
  }

  async function onDelete(id: string, name: string) {
    setBusy(true);
    try {
      await deleteFromLibrary(id);
      setStatus(`Deleted ${name}`);
      if (playing === id) stopAudio();
      onTrackDeleted?.(id);
      await refresh();
    } catch (err) {
      setStatus("⚠️ " + (err instanceof Error ? err.message : "delete failed"));
    } finally {
      setBusy(false);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.add("drag-over");
  }

  function handleDragLeave() {
    dropRef.current?.classList.remove("drag-over");
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.remove("drag-over");
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        stopAudio();
        const name = `recording-${Date.now()}.webm`;
        await uploadFile(new File([blob], name));
      };
      rec.start();
      mediaRef.current = rec;
      setRecording(true);
      setRecordTimer(0);
      setStatus("Recording…");
      recordTimerRef.current = setInterval(() => {
        setRecordTimer((t) => t + 1);
      }, 1000);
    } catch (err) {
      setStatus("⚠️ " + (err instanceof Error ? err.message : "Mic access denied"));
    }
  }

  function stopRecording() {
    if (recordTimerRef.current) clearInterval(recordTimerRef.current);
    recordTimerRef.current = null;
    mediaRef.current?.stop();
    mediaRef.current = null;
    setRecording(false);
    setRecordTimer(0);
  }

  const nowPlaying = files.find((f) => f.id === playing);

  return (
    <div className="card">
      <h3 className="card-title"><span className="glyph">▤</span> Library</h3>

      <div
        ref={dropRef}
        className={`drop-zone${!signedIn ? " disabled" : ""}`}
        onDragOver={signedIn ? handleDragOver : undefined}
        onDragLeave={signedIn ? handleDragLeave : undefined}
        onDrop={signedIn ? handleDrop : undefined}
        onClick={() => signedIn && !recording && inputRef.current?.click()}
        style={{ opacity: recording ? 0.4 : 1, pointerEvents: recording ? "none" : "auto" }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="audio/*,.musicxml,.mid,.midi"
          onChange={onUpload}
          disabled={busy || !signedIn}
          style={{ display: "none" }}
        />
        <span className="drop-icon">+</span>
        <span className="muted">{signedIn ? "Drop audio or MusicXML to save to your library" : "Sign in to save audio to your library"}</span>
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>WAV · MP3 · M4A · MusicXML · MIDI</span>
      </div>

      <div className="toolbar">
        <button className="icon-btn" onClick={recording ? stopRecording : startRecording} disabled={busy || !signedIn}>
          {recording ? "■ Stop" : "● Record"}
        </button>
      </div>

      {recording && (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", marginTop: "var(--s-2)" }}>
          <span className="record-dot" />
          <span className="muted" style={{ fontFamily: "monospace" }}>
            {formatTime(recordTimer)}
          </span>
        </div>
      )}

      {playing && nowPlaying && (
        <div className="card" style={{ marginTop: "var(--s-3)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--s-1)" }}>
            <span style={{ fontWeight: 500, fontSize: "var(--fs-sm)" }}>{nowPlaying.name}</span>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
              <span className="muted" style={{ fontFamily: "monospace", fontSize: "var(--fs-xs)" }}>
                {formatTime(currentTime)} / {formatTime(duration || 0)}
              </span>
              <button className="icon-btn ghost" onClick={stopAudio} title="Close" style={{ fontSize: "var(--fs-xs)", padding: 0, lineHeight: 1 }}>✕</button>
            </div>
          </div>
          <div
            className="pb-track"
            style={{ height: 4, marginBottom: 4 }}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              if (rect.width === 0) return;
              const pct = (e.clientX - rect.left) / rect.width;
              const a = audioRef.current;
              if (a && duration > 0 && pct >= 0 && pct <= 1) a.currentTime = pct * duration;
            }}
          >
            <div className="pb-fill" style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }} />
          </div>
          <Visualizer audioRef={audioRef} />
          <div className="toolbar" style={{ justifyContent: "center" }}>
            <button className="icon-btn" onClick={() => paused ? resume() : pause()}>
              {paused ? "▶" : "⏸"}
            </button>
          </div>
        </div>
      )}

      <span className="status">{status}</span>

      {signedIn ? (
        <>
          <div className="section-label">Tracks</div>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
              {[1, 2, 3].map((i) => (
                <div key={i} className="track" style={{ opacity: 0.5 }}>
                  <div className="track-head">
                    <div className="track-name"><div className="skel line" style={{ width: "60%" }} /></div>
                    <div className="track-actions"><div className="skel" style={{ width: 60, height: 28, borderRadius: "var(--r-full)" }} /></div>
                  </div>
                </div>
              ))}
            </div>
          ) : files.length === 0 ? (
            <div className="empty">No tracks yet. Transcribe audio and save it here.</div>
          ) : (
            files.map((f) => {
              const state = deriveTrackState(f);
              return (
                <div key={f.id} className="track">
                  <div className="track-head">
                    <div className="track-name">{f.name}</div>
                    <div className="track-meta">{f.size ? formatSize(f.size) : ""}</div>
                    <div className="track-actions">
                      <button className="icon-btn" onClick={() => togglePlay(f.id, f.url)}>
                        {playing === f.id && !paused ? "⏸" : "▶"}
                      </button>
                      {onTranscribe && (
                        <button
                          className={`icon-btn ${!state.transcribed ? "" : "ghost"}`}
                          onClick={() => onTranscribe(f)}
                          disabled={isTranscribing || isAnalyzing}
                        >
                          {state.transcribed ? "View Transcription" : "Transcribe"}
                        </button>
                      )}
                      {onVisualize && state.transcribed && (
                        <button className="icon-btn ghost" onClick={() => onVisualize(f)}>
                          Visualize
                        </button>
                      )}
                      {onAnalyze && state.transcribed && (
                        <button
                          className={`icon-btn ${!state.analysis ? "" : "ghost"}`}
                          onClick={() => onAnalyze(f)}
                          disabled={isTranscribing || isAnalyzing}
                        >
                          {state.analysis ? "View Analysis" : "Analyze"}
                        </button>
                      )}
                      <button className="icon-btn ghost danger" onClick={() => onDelete(f.id, f.name)} disabled={busy}>
                        ✕
                      </button>
                    </div>
                  </div>
                  <div className="track-artifacts">
                    <span className="artifact done"><span className="dot" /> Audio</span>
                    {state.transcribed && (
                      <span className="artifact done"><span className="dot" /> Transcribed</span>
                    )}
                    {state.sheetMusic && (
                      <span className="artifact done"><span className="dot" /> Sheet Music</span>
                    )}
                    {state.analysis && (
                      <span className="artifact done"><span className="dot" /> Analyzed</span>
                    )}
                    {!state.transcribed && (
                      <span className="artifact pending"><span className="dot" /> Not transcribed</span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </>
      ) : (
        <div className="empty" style={{ marginTop: "var(--s-4)" }}>
          Sign in to view and manage your tracks.
        </div>
      )}

    </div>
  );
}
