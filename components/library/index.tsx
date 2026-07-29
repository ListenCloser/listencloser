"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { isSupabaseConfigured } from "@/lib/supabase";
import {
  uploadToLibrary,
  listLibrary,
  deleteFromLibrary,
  deriveTrackState,
  type LibFile,
} from "@/lib/music";
import { useSharedAudio } from "@/lib/audio-context";

function formatSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(sec?: number): string {
  if (!sec) return "";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function Library({
  signedIn,
  onSignIn,
  onTrackSelect,
  onTrackDeleted,
  refreshKey,
  selectedTrackId,
}: {
  signedIn?: boolean;
  onSignIn?: () => void;
  onTrackSelect?: (file: LibFile) => void;
  onTrackDeleted?: (id: string) => void;
  refreshKey?: number;
  selectedTrackId?: string;
}) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<LibFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);
  const [recordTimer, setRecordTimer] = useState(0);

  const { playing, paused, toggle: togglePlay, stop: stopAudio } = useSharedAudio();

  const dropRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    if (!isSupabaseConfigured) { setLoading(false); return; }
    setLoading(true);
    try {
      setFiles(await listLibrary());
    } catch (e) {
      setStatus("Failed to load library");
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
    setStatus("Uploading...");
    try {
      await uploadToLibrary(file.name, file);
      setStatus(`Uploaded ${file.name}`);
      await refresh();
    } catch (err) {
      setStatus("Upload failed");
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

  async function onDelete(id: string, name: string, e: React.MouseEvent) {
    e.stopPropagation();
    setBusy(true);
    try {
      await deleteFromLibrary(id);
      setStatus(`Deleted ${name}`);
      if (playing === id) stopAudio();
      onTrackDeleted?.(id);
      await refresh();
    } catch (err) {
      setStatus("Delete failed");
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
        const name = `recording-${Date.now()}.webm`;
        await uploadFile(new File([blob], name));
      };
      rec.start();
      mediaRef.current = rec;
      setRecording(true);
      setRecordTimer(0);
      setStatus("Recording...");
      recordTimerRef.current = setInterval(() => {
        setRecordTimer((t) => t + 1);
      }, 1000);
    } catch (err) {
      setStatus("Microphone access denied");
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

  return (
    <>
      <div className="sidebar-header">
        <div className="brand">
          <span className="brand-dot" />
          Library
        </div>
        {signedIn ? (
          <button className="btn btn-ghost btn-sm" onClick={onSignIn}>Sign out</button>
        ) : (
          <button className="btn btn-ghost btn-sm" id="signInBtn" onClick={onSignIn}>Sign in</button>
        )}
      </div>

      <div className="sidebar-content">
        <div
          ref={dropRef}
          className={`upload-zone${!signedIn ? " disabled" : ""}`}
          onDragOver={signedIn ? handleDragOver : undefined}
          onDragLeave={signedIn ? handleDragLeave : undefined}
          onDrop={signedIn ? handleDrop : undefined}
          onClick={() => signedIn && !recording && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept="audio/*,.musicxml,.mid,.midi"
            onChange={onUpload}
            disabled={busy || !signedIn}
            style={{ display: "none" }}
          />
          <span className="upload-icon">+</span>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
            {signedIn ? "Drop audio or click to upload" : "Sign in to upload"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-3)" }}>
          <button
            className="btn btn-sm"
            style={{ flex: 1 }}
            onClick={recording ? stopRecording : startRecording}
            disabled={busy || !signedIn}
          >
            {recording ? (
              <><span className="record-dot" /> Stop ({Math.floor(recordTimer / 60)}:{(recordTimer % 60).toString().padStart(2, "0")})</>
            ) : (
              "Record"
            )}
          </button>
        </div>

        {status && <div className="status" style={{ marginBottom: "var(--s-2)" }}>{status}</div>}

        {!signedIn ? (
          <div className="empty-state" style={{ marginTop: "var(--s-4)" }}>
            Sign in to manage your music library
          </div>
        ) : loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ padding: "var(--s-3)", borderRadius: "var(--r-md)" }}>
                <div className="skel line" style={{ width: "60%", marginBottom: "var(--s-2)" }} />
                <div className="skel line" style={{ width: "40%" }} />
              </div>
            ))}
          </div>
        ) : files.length === 0 ? (
          <div className="empty-state">No tracks yet</div>
        ) : (
          files.map((f) => {
            const state = deriveTrackState(f);
            const isSelected = selectedTrackId === f.id;
            const isCurrentlyPlaying = playing === f.id;
            return (
              <div
                key={f.id}
                className={`lib-item${isSelected ? " selected" : ""}`}
                onClick={() => onTrackSelect?.(f)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
                  <div className="lib-item-name" style={{ flex: 1 }}>{f.name}</div>
                  <button
                    className="icon-btn"
                    onClick={(e) => { e.stopPropagation(); togglePlay(f.id, f.url); }}
                    title={isCurrentlyPlaying && !paused ? "Pause" : "Play"}
                    style={{ width: 24, height: 24, fontSize: 10 }}
                  >
                    {isCurrentlyPlaying && !paused ? "⏸" : "▶"}
                  </button>
                  <button
                    className="icon-btn danger"
                    onClick={(e) => onDelete(f.id, f.name, e)}
                    disabled={busy}
                    title="Delete"
                    style={{ width: 24, height: 24, fontSize: 10 }}
                  >
                    ×
                  </button>
                </div>
                <div className="lib-item-meta">
                  {f.size && <span>{formatSize(f.size)}</span>}
                  {f.created_at && <span>{timeAgo(f.created_at)}</span>}
                  {f.analysis?.tempo && <span>{Math.round(f.analysis.tempo.bpm)} BPM</span>}
                  {f.analysis?.key && <span>{f.analysis.key.tonic} {f.analysis.key.mode}</span>}
                </div>
                <div className="lib-item-badges">
                  <span className="badge done"><span className="badge-dot" /> Audio</span>
                  {state.transcribed && <span className="badge done"><span className="badge-dot" /> MIDI</span>}
                  {state.sheetMusic && <span className="badge done"><span className="badge-dot" /> Score</span>}
                  {state.analysis && <span className="badge done"><span className="badge-dot" /> Analysis</span>}
                  {!state.transcribed && <span className="badge"><span className="badge-dot" /> Not processed</span>}
                </div>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
