"use client";

import { useEffect, useState, useRef } from "react";
import {
  transcribeAudio,
  enhanceAudio,
  analyzeAudio,
  listLibrary,
  uploadToLibrary,
  saveTranscription,
  blobToBase64,
  convertMusicFormat,
  synthAudio,
  type TranscribeResult,
  type LibFile,
} from "@/lib/music";
import { saveLocalTranscription, loadLocalTranscription, clearLocalTranscription } from "@/lib/browser-store";
import { useAuth } from "@/components/AuthProvider";
import PianoRoll from "@/components/PianoRoll";
import SheetMusic from "@/components/SheetMusic";
import Visualizer from "@/components/Visualizer";

type Mode = "transcribe" | "midi-to-score";
type State = "idle" | "enhancing" | "transcribing" | "converting" | "synthing" | "populated" | "error";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "transcribe", label: "Audio → MIDI", hint: "Transcribe audio to MIDI" },
  { id: "midi-to-score", label: "MIDI → Sheet Music", hint: "Convert MIDI to sheet music" },
];

function audioFmtFromBlob(blob: Blob): string {
  const type = blob.type.toLowerCase();
  if (type.includes("ogg")) return "ogg";
  if (type.includes("mp4") || type.includes("m4a")) return "mp4";
  if (type.includes("flac")) return "flac";
  if (type.includes("mp3") || type.includes("mpeg")) return "mp3";
  return "wav";
}

function audioFmtFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["ogg", "mp4", "m4a", "flac", "mp3", "wav", "webm"].includes(ext)) return ext === "m4a" ? "mp4" : ext;
  return "wav";
}

export default function Transform({
  signedIn,
  onTranscribed,
  onGoToAnalyze,
  onAnalyze,
  libraryFileToLoad,
  onClearLibraryFile,
  onTranscriptionSaved,
  onBusyChange,
  onNewTranscription,
  analysis,
  initialResult,
  initialAudioName,
}: {
  signedIn?: boolean;
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onGoToAnalyze?: () => void;
  onAnalyze?: (midiBase64?: string, name?: string, libraryFileId?: string) => void;
  libraryFileToLoad?: LibFile | null;
  onClearLibraryFile?: () => void;
  onTranscriptionSaved?: () => void;
  onBusyChange?: (busy: boolean) => void;
  onNewTranscription?: () => void;
  analysis?: TranscribeResult["analysis"] | null;
  initialResult?: TranscribeResult | null;
  initialAudioName?: string;
}) {
  const { user } = useAuth();
  const [mode, setMode] = useState<Mode>("transcribe");
  const [state, setState] = useState<State>(() => initialResult ? "populated" : "idle");
  const [result, setResult] = useState<TranscribeResult | null>(initialResult ?? null);
  const [audioName, setAudioName] = useState(initialAudioName ?? "");
  const [analyzeBase64, setAnalyzeBase64] = useState("");
  const [status, setStatus] = useState("");
  const [libFiles, setLibFiles] = useState<LibFile[]>([]);
  const [showLibPicker, setShowLibPicker] = useState(false);
  const [recording, setRecording] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [saved, setSaved] = useState(false);
  const [wasLibraryFile, setWasLibraryFile] = useState(false);
  const [libraryFileId, setLibraryFileId] = useState<string | null>(null);
  const originalBlobRef = useRef<Blob | null>(null);
  const [wavUrl, setWavUrl] = useState("");
  const [wavPlaying, setWavPlaying] = useState(false);
  const [musicXml, setMusicXml] = useState("");

  useEffect(() => {
    listLibrary()
      .then(setLibFiles)
      .catch((err) => {
        setStatus(
          "⚠️ Could not load your library: " +
            (err instanceof Error ? err.message : "unknown error"),
        );
      });
  }, []);

  useEffect(() => {
    return () => {
      if (wavUrl) URL.revokeObjectURL(wavUrl);
    };
  }, []);

  useEffect(() => {
    onBusyChange?.(state === "enhancing" || state === "transcribing" || state === "converting" || state === "synthing");
  }, [state, onBusyChange]);

  useEffect(() => {
    if (libraryFileToLoad) {
      setMode("transcribe");
      onSelectLibraryFile(libraryFileToLoad);
      onClearLibraryFile?.();
    }
  }, [libraryFileToLoad]);

  async function processBlob(blob: Blob, fileName: string, fmtOverride?: string, sourceLibId?: string | null) {
    clearLocalTranscription();
    onNewTranscription?.();
    setResult(null);
    setShowLibPicker(false);
    setPlayhead(0);
    setWasLibraryFile(false);
    setMusicXml("");
    originalBlobRef.current = blob;

    try {
      const b64 = await blobToBase64(blob);
      const fmt = fmtOverride ?? audioFmtFromBlob(blob);

      setState("enhancing");
      setStatus("Cleaning audio…");
      let transcribeBase64 = b64;
      try {
        const clean = await enhanceAudio(b64, fmt);
        if (clean.wav_base64) transcribeBase64 = clean.wav_base64;
      } catch {
        setStatus("Cleaning skipped — transcribing raw audio…");
      }

      setState("transcribing");
      setStatus("Transcribing…");
      const res = await transcribeAudio(transcribeBase64, fmt);
      setResult(res);
      setAnalyzeBase64(transcribeBase64);
      onTranscribed?.(res, fileName);

      if (res.midi_base64) {
        setState("synthing");
        setStatus("Synthesizing audio…");
        try {
          const synth = await synthAudio(res.midi_base64);
          const bytes = Uint8Array.from(atob(synth.wav_base64), (c) => c.charCodeAt(0));
          const blob = new Blob([bytes], { type: "audio/wav" });
          if (wavUrl) URL.revokeObjectURL(wavUrl);
          setWavUrl(URL.createObjectURL(blob));
        } catch {
          // synth failed, will fall back to MIDI display only
        }
      }

      setState("populated");
      setStatus(`${res.num_notes} notes extracted`);

      if (signedIn && res.notes.length > 0) {
        try {
          let savedId: string;
          if (sourceLibId) {
            savedId = sourceLibId;
          } else {
            const { id } = await uploadToLibrary(fileName || "audio", originalBlobRef.current!);
            savedId = id;
          }
          setLibraryFileId(savedId);

          let analysisResult: TranscribeResult["analysis"] = res.analysis ?? undefined;
          if (!analysisResult && res.midi_base64) {
            try {
              analysisResult = await analyzeAudio(res.midi_base64);
              setAnalyzeBase64(res.midi_base64);
            } catch {
              // analysis failed, continue without it
            }
          }

          await saveTranscription(savedId, res.notes, res.midi_base64, analysisResult);
          setSaved(true);
          onTranscriptionSaved?.();
        } catch (e) {
          console.error("auto-save failed", e);
        }
      } else if (!signedIn && res.notes.length > 0) {
        let analysisResult: TranscribeResult["analysis"] = res.analysis ?? undefined;
        if (!analysisResult && res.midi_base64) {
          try {
            analysisResult = await analyzeAudio(res.midi_base64);
            setAnalyzeBase64(res.midi_base64);
          } catch {
            // analysis failed, continue without it
          }
        }
        saveLocalTranscription(fileName, res.notes, res.midi_base64, originalBlobRef.current ?? undefined, analysisResult);
      }
    } catch (err) {
      setState("error");
      setStatus("⚠️ " + (err instanceof Error ? err.message : "transcription failed"));
    }
  }

  async function handleMidiFile(file: File) {
    clearLocalTranscription();
    onNewTranscription?.();
    setAudioName(file.name);
    setResult(null);
    setShowLibPicker(false);
    setMusicXml("");
    setState("converting");
    setStatus("Converting MIDI to sheet music…");

    try {
      const b64 = await blobToBase64(file);
      const converted = await convertMusicFormat(b64, "midi", "musicxml");
      setMusicXml(atob(converted.data_base64));
      setResult({
        notes: [],
        num_notes: 0,
        midi_base64: b64,
      });
      setState("populated");
      setStatus("Sheet music ready");
    } catch (err) {
      setState("error");
      setStatus("⚠️ " + (err instanceof Error ? err.message : "conversion failed"));
    }
  }

  async function handleFilePick(file: File) {
    setAudioName(file.name);
    if (mode === "midi-to-score") {
      await handleMidiFile(file);
    } else {
      await processBlob(file, file.name);
    }
  }

  function onUploadNew(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    handleFilePick(file);
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      mediaRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => chunksRef.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const mimeType = rec.mimeType || "audio/webm";
        const ext = mimeType.includes("ogg") ? "ogg" : "webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const name = `recording-${Date.now()}.${ext}`;
        setAudioName(name);
        await processBlob(blob, name);
      };
      rec.start();
      setRecording(true);
      setStatus("Recording…");
    } catch (err) {
      setState("error");
      setStatus("⚠️ " + (err instanceof Error ? err.message : "recording failed"));
    }
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  function reset() {
    if (wavUrl) URL.revokeObjectURL(wavUrl);
    setWavUrl("");
    setWavPlaying(false);
    setState("idle");
    setResult(null);
    setAudioName("");
    setAnalyzeBase64("");
    setStatus("");
    setShowLibPicker(false);
    setPlayhead(0);
    setSaved(false);
    setWasLibraryFile(false);
    setLibraryFileId(null);
    originalBlobRef.current = null;
    setMusicXml("");
  }

  async function saveToLibrary() {
    if (!result) return;
    if (wasLibraryFile) {
      setSaved(true);
      setStatus("✓ Already in library");
      return;
    }
    try {
      setStatus("Saving to library…");
      const blob = originalBlobRef.current;
      if (!blob) return;
      const { id } = await uploadToLibrary(audioName || "audio", blob);
      if (result.notes.length) {
        await saveTranscription(id, result.notes, result.midi_base64);
      }
      setLibraryFileId(id);
      setSaved(true);
      onTranscriptionSaved?.();
      setStatus("✓ Saved to library");
    } catch (err) {
      setStatus("⚠️ " + (err instanceof Error ? err.message : "save failed"));
    }
  }

  async function onSelectLibraryFile(file: LibFile) {
    setAudioName(file.name);
    setShowLibPicker(false);
    setWasLibraryFile(true);
    setLibraryFileId(file.id);
    setMusicXml("");
    setPlayhead(0);
    audioRef.current?.pause();
    setWavPlaying(false);

    if (mode === "midi-to-score") {
      const midiB64 = file.midi_base64;
      if (!midiB64) {
        setState("error");
        setStatus("⚠️ No MIDI data available for this track");
        return;
      }
      setState("converting");
      setStatus("Converting to sheet music…");
      try {
        const converted = await convertMusicFormat(midiB64, "midi", "musicxml");
        setMusicXml(atob(converted.data_base64));
        setResult({
          notes: file.notes ?? [],
          num_notes: file.notes?.length ?? 0,
          midi_base64: midiB64,
        });
        setState("populated");
        setStatus("Sheet music ready");
      } catch {
        setState("error");
        setStatus("⚠️ Could not convert to sheet music");
      }
      return;
    }

    // Audio → MIDI mode
    if (file.notes && file.notes.length > 0) {
      setResult({
        notes: file.notes,
        num_notes: file.notes.length,
        midi_base64: file.midi_base64,
        wav_url: file.url,
      });
      setState("populated");
      setStatus(`${file.notes.length} notes loaded from library`);
      return;
    }

    setState("transcribing");
    setStatus("Transcribing from library…");
    try {
      const res = await transcribeAudio(undefined, audioFmtFromName(file.name), file.id);
      setResult(res);
      setAnalyzeBase64(res.wav_base64 ?? "");
      onTranscribed?.(res, file.name);

      setState("populated");
      setStatus(`${res.num_notes} notes extracted`);

      if (signedIn && res.notes.length > 0) {
        try {
          await saveTranscription(file.id, res.notes, res.midi_base64);
          setSaved(true);
          onTranscriptionSaved?.();
        } catch (e) {
          console.error("auto-save transcription failed", e);
        }
      }
    } catch (err) {
      setState("error");
      setStatus("⚠️ " + (err instanceof Error ? err.message : "transcription failed"));
    }
  }

  function downloadMusicXml() {
    if (!musicXml) return;
    const blob = new Blob([musicXml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = audioName.replace(/\.[^.]+$/, "") + ".musicxml";
    a.click();
    URL.revokeObjectURL(url);
  }

  const canUseLibrary = signedIn && libFiles.length > 0;
  const localTranscription = !signedIn ? loadLocalTranscription() : null;
  const midiTranscriptions = libFiles.filter((f) => f.midi_base64);
  const isBusy = state === "enhancing" || state === "transcribing" || state === "converting" || state === "synthing";

  return (
    <div className="card">
      <h3 className="card-title"><span className="glyph">♪</span> Transform</h3>

      <div className="section-label">Mode</div>
      <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-3)", flexWrap: "wrap" }}>
        {MODES.map((m) => (
          <button
            key={m.id}
            className={`chip${mode === m.id ? "" : " ghost"}`}
            onClick={() => {
              if (mode !== m.id && !isBusy) {
                setMode(m.id);
                setShowLibPicker(false);
              }
            }}
            disabled={isBusy && mode !== m.id}
            title={m.hint}
          >
            {m.label}
          </button>
        ))}
      </div>

      {state === "idle" && !showLibPicker && (
        <>
          <div className="section-label">
            {mode === "transcribe" && "Choose an audio source"}
            {mode === "midi-to-score" && "MIDI → Sheet Music"}
          </div>

          {mode === "transcribe" && (
            <div className="source-grid">
              <div className="source-card" onClick={() => inputRef.current?.click()}>
                <span className="sc-icon">⬆</span>
                <span className="sc-label">Upload file</span>
                <span className="sc-hint">WAV · MP3 · M4A</span>
                <input
                  ref={inputRef}
                  type="file"
                  accept="audio/*"
                  onChange={onUploadNew}
                  style={{ display: "none" }}
                />
              </div>
              <div className="source-card" onClick={recording ? stopRecording : startRecording}>
                <span className="sc-icon">{recording ? "■" : "●"}</span>
                <span className="sc-label">{recording ? "Stop" : "Record"}</span>
                <span className="sc-hint">Use your mic</span>
              </div>
              {signedIn && canUseLibrary && (
                <div className="source-card" onClick={() => setShowLibPicker(true)}>
                  <span className="sc-icon">▤</span>
                  <span className="sc-label">From library</span>
                  <span className="sc-hint">{libFiles.length === 0 ? "No saved tracks" : "Pick a track"}</span>
                </div>
              )}
            </div>
          )}

          {mode === "midi-to-score" && !signedIn && (
            localTranscription?.midi_base64 ? (
              <div style={{ textAlign: "center", padding: "var(--s-4)" }}>
                <p className="muted" style={{ margin: "0 0 var(--s-3)" }}>
                  Using: <strong>{localTranscription.name}</strong>
                </p>
                <button className="btn btn-primary" onClick={() => {
                  const localFile: LibFile = {
                    name: localTranscription.name,
                    url: localTranscription.audioDataUrl || "",
                    id: "__local__",
                    notes: localTranscription.notes,
                    midi_base64: localTranscription.midi_base64,
                  };
                  onSelectLibraryFile(localFile);
                }}>
                  Convert to Sheet Music
                </button>
              </div>
            ) : (
              <p className="muted" style={{ fontSize: "var(--fs-sm)", textAlign: "center", padding: "var(--s-4)" }}>
                Transcribe an audio song first — then come back for sheet music.
              </p>
            )
          )}

          {mode === "midi-to-score" && signedIn && (
            <div className="source-grid">
              <div className="source-card" onClick={() => inputRef.current?.click()}>
                <span className="sc-icon">⬆</span>
                <span className="sc-label">Upload MIDI</span>
                <span className="sc-hint">.mid files</span>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".mid,.midi"
                  onChange={onUploadNew}
                  style={{ display: "none" }}
                />
              </div>
              {canUseLibrary && (
                <div className="source-card" onClick={() => setShowLibPicker(true)}>
                  <span className="sc-icon">▤</span>
                  <span className="sc-label">From library</span>
                  <span className="sc-hint">{midiTranscriptions.length === 0 ? "No transcriptions" : "Pick a track"}</span>
                </div>
              )}
            </div>
          )}

          {!signedIn && mode === "transcribe" && (
            <p className="muted" style={{ fontSize: "var(--fs-sm)", textAlign: "center" }}>
              Transcribe freely — sign in to save results to your library.
            </p>
          )}
        </>
      )}

      {showLibPicker && (
        <>
          <div className="section-label">
            {mode === "midi-to-score" ? "Pick a transcription with MIDI" : "Pick a saved track"}
          </div>
          {(!signedIn && localTranscription) ? (
            <div
              key="__local__"
              className="track"
              style={{ cursor: "pointer" }}
              onClick={() => {
                const localFile: LibFile = {
                  name: localTranscription.name,
                  url: localTranscription.audioDataUrl || "",
                  id: "__local__",
                  notes: localTranscription.notes,
                  midi_base64: localTranscription.midi_base64,
                };
                onSelectLibraryFile(localFile);
              }}
            >
              <div className="track-head">
                <div className="track-name">{localTranscription.name}</div>
                <div className="track-actions">
                  <span className="chip" style={{ fontSize: "var(--fs-xs)" }}>
                    {mode === "midi-to-score" ? "Convert" : "View"}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <>
              {(mode === "midi-to-score" ? midiTranscriptions : libFiles).map((f) => (
                <div key={f.id} className="track" style={{ cursor: "pointer" }} onClick={() => onSelectLibraryFile(f)}>
                  <div className="track-head">
                    <div className="track-name">{f.name}</div>
                    <div className="track-actions">
                      <span className="chip" style={{ fontSize: "var(--fs-xs)" }}>
                        {mode === "midi-to-score" ? "Convert" : (f.notes && f.notes.length > 0 ? "View" : "Transcribe")}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {(mode === "midi-to-score" && midiTranscriptions.length === 0) && (
                <p className="muted" style={{ fontSize: "var(--fs-sm)", textAlign: "center", padding: "var(--s-4)" }}>
                  No transcriptions with MIDI data yet. Transcribe an audio track first.
                </p>
              )}
            </>
          )}
          <div className="toolbar">
            <button className="btn btn-ghost" onClick={() => setShowLibPicker(false)}>Back</button>
          </div>
        </>
      )}

      {isBusy && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", margin: "var(--s-3) 0" }}>
            <span className="chip-q major" style={{ borderRadius: "var(--r-md)" }}>{audioName || "audio"}</span>
            <span className="status" style={{ fontSize: "var(--fs-sm)" }}>{status}</span>
          </div>
          {(() => {
            const done = (s: State) => s === "populated";
            const steps: { label: string; active: boolean; done: boolean }[] = [
              { label: "Clean", active: state === "enhancing", done: done(state) || state === "transcribing" || state === "converting" || state === "synthing" },
              { label: mode === "midi-to-score" ? "Convert" : "Transcribe", active: state === "transcribing" || state === "converting", done: done(state) || state === "synthing" },
            ];
            if (mode === "transcribe") steps.push({ label: "Synthesize", active: state === "synthing", done: done(state) });
            return (
              <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-2)" }}>
                {steps.map((step, i) => (
                  <div key={i} style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: "var(--fs-xs)", color: step.active ? "var(--text)" : "var(--muted)" }}>
                        {i + 1}. {step.label}
                      </span>
                      <span style={{ fontSize: "var(--fs-xs)", color: step.active ? "var(--accent)" : step.done ? "var(--success)" : "var(--muted)" }}>
                        {step.active ? "…" : step.done ? "✓" : ""}
                      </span>
                    </div>
                    <div style={{ height: 4, background: "var(--panel-3)", borderRadius: "var(--r-full)" }}>
                      <div className={step.active ? "pulse" : ""} style={{ height: "100%", width: step.done ? "100%" : step.active ? "60%" : "0%", background: step.done ? "var(--success)" : "var(--accent)", borderRadius: "var(--r-full)", transition: "width 0.3s" }} />
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}
        </>
      )}

      {state === "populated" && result && (
        <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "var(--s-2)" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "var(--fs-base)" }}>{audioName}</h3>
                <p className="muted" style={{ margin: "var(--s-1) 0 0" }}>
                  {musicXml ? "Sheet music" : `${result.num_notes} notes`}
                </p>
              </div>
              <div style={{ display: "flex", gap: "var(--s-2)" }}>
                {!saved && signedIn && result && !wasLibraryFile && (
                  <button className="btn" onClick={saveToLibrary}>
                    Save to library
                  </button>
                )}
              {saved && signedIn && (
                <span className="chip" style={{ cursor: "default" }}>
                  {wasLibraryFile ? "✓ In library" : "✓ Saved"}
                </span>
              )}
              {result?.midi_base64 && mode === "transcribe" && (
                <button className="btn" onClick={() => {
                  const bytes = Uint8Array.from(atob(result.midi_base64!), (c) => c.charCodeAt(0));
                  const blob = new Blob([bytes], { type: "audio/midi" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = (audioName || "midi").replace(/\.[^.]+$/, "") + ".mid";
                  a.click();
                  URL.revokeObjectURL(url);
                }}>
                  Download MIDI
                </button>
              )}
              {result?.midi_base64 && mode === "midi-to-score" && !musicXml && (
                <button className="btn btn-primary" onClick={async () => {
                  setState("converting");
                  setStatus("Converting to sheet music…");
                  try {
                    const converted = await convertMusicFormat(result.midi_base64!, "midi", "musicxml");
                    setMusicXml(atob(converted.data_base64));
                    setStatus("Sheet music ready");
                    setState("populated");
                  } catch (err) {
                    setStatus("⚠️ " + (err instanceof Error ? err.message : "conversion failed"));
                    setState("populated");
                  }
                }}>
                  Convert to Sheet Music
                </button>
              )}
              {musicXml && mode === "midi-to-score" && (
                <button className="btn" onClick={downloadMusicXml}>
                  Export MusicXML
                </button>
              )}
              {onGoToAnalyze && onAnalyze && result && result.notes.length > 0 && mode === "transcribe" && (
                  <button
                    className="btn btn-primary"
                    onClick={async () => {
                      try {
                        await onAnalyze(result.midi_base64, audioName, libraryFileId ?? undefined);
                      } catch {
                        /* analysisError surfaces on the Analyze tab */
                      }
                      onGoToAnalyze();
                    }}
                  >
                    {analysis ? "View Analysis" : "Analyze"}
                  </button>
              )}
              <button className="btn btn-ghost" onClick={reset}>✕ Clear</button>
            </div>
          </div>

          {musicXml && mode === "midi-to-score" && (
            <>
              <div className="section-label">Sheet music</div>
              <SheetMusic musicXml={musicXml} />
            </>
          )}

          {mode === "transcribe" && result && result.notes.length > 0 && (
            <>
              <div className="section-label">Playback</div>
              {wavUrl ? (
                <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", marginBottom: "var(--s-2)" }}>
                  <button className="icon-btn" onClick={() => {
                    const a = audioRef.current;
                    if (!a) return;
                    if (a.paused) {
                      a.play().catch(() => {});
                      setWavPlaying(true);
                    } else {
                      a.pause();
                      setWavPlaying(false);
                    }
                  }}>
                    {wavPlaying ? "⏸" : "▶"}
                  </button>
                  <span className="muted" style={{ fontFamily: "monospace", fontSize: "var(--fs-xs)" }}>
                    {Math.floor(playhead)}s — Audio
                  </span>
                </div>
              ) : (
                <p className="muted" style={{ fontSize: "var(--fs-sm)" }}>Audio synthesis unavailable</p>
              )}
              <audio
                ref={audioRef}
                src={wavUrl}
                onTimeUpdate={(e) => setPlayhead(e.currentTarget.currentTime)}
                onPlay={() => setWavPlaying(true)}
                onPause={() => setWavPlaying(false)}
                onEnded={() => { setWavPlaying(false); setPlayhead(0); }}
                style={{ display: "none" }}
              />

              {wavUrl && <Visualizer audioRef={audioRef} />}

              <div className="section-label">Piano roll</div>
              <div className="card">
                <PianoRoll
                  notes={result.notes}
                  playheadTime={playhead}
                  bpm={result.analysis?.tempo?.bpm ?? 120}
                />
              </div>
            </>
          )}
        </>
      )}

      {state === "error" && (
        <div className="alert-danger" style={{ marginTop: "var(--s-3)" }}>
          <p className="status" style={{ color: "var(--danger)", margin: 0 }}>{status}</p>
          <button className="btn" onClick={reset}>Try again</button>
        </div>
      )}
    </div>
  );
}
