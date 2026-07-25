"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { listLibrary, synthAudio, synthMusicXml, convertMusicFormat, formatTime, type LibFile } from "@/lib/music";
import { loadLocalTranscription } from "@/lib/browser-store";
import PianoRoll from "@/components/PianoRoll";
import Spectrogram from "@/components/Spectrogram";
import ChromaHeatmap from "@/components/ChromaHeatmap";
import Tonnetz from "@/components/Tonnetz";
import Visualizer from "@/components/Visualizer";
import SheetMusic from "@/components/SheetMusic";
import { useSharedAudio } from "@/lib/audio-context";

type VizMode = "piano-roll" | "spectrogram" | "chroma" | "tonnetz" | "sheet-music";
type PlaybackSource = "original" | "midi" | "sheet-music";

const VIZ_MODES: { id: VizMode; label: string }[] = [
  { id: "piano-roll", label: "Piano roll" },
  { id: "spectrogram", label: "Spectrogram" },
  { id: "chroma", label: "Chroma" },
  { id: "tonnetz", label: "Tonnetz" },
  { id: "sheet-music", label: "Sheet Music" },
];

export default function Viz({
  initialTrackId,
  selectedId: selectedIdProp,
  onTrackSelected,
  onStopRef,
}: {
  initialTrackId?: string | null;
  selectedId?: string;
  onTrackSelected?: (id: string) => void;
  onStopRef?: React.MutableRefObject<(() => void) | null>;
}) {
  const [files, setFiles] = useState<LibFile[]>([]);
  const [selectedIdLocal, setSelectedIdLocal] = useState<string>("");
  const selectedId = selectedIdProp ?? selectedIdLocal;
  const [mode, setMode] = useState<VizMode>("piano-roll");
  const [playbackSource, setPlaybackSource] = useState<PlaybackSource>("midi");
  const [midiTime, setMidiTime] = useState(0);
  const [musicXml, setMusicXml] = useState("");
  const [midiDuration, setMidiDuration] = useState(0);
  const midiIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const midiStartRef = useRef(0);
  const midiOffsetRef = useRef(0);
  const [midiWavUrl, setMidiWavUrl] = useState<string | null>(null);
  const [sheetWavUrl, setSheetWavUrl] = useState<string | null>(null);
  const [synthLoading, setSynthLoading] = useState(false);
  const [sheetMusicLoading, setSheetMusicLoading] = useState(false);
  const [useFallbackTimer, setUseFallbackTimer] = useState(false);

  const { playing, currentTime, duration, play, stop: sharedStop, audioRef } = useSharedAudio();

  useEffect(() => {
    const local = loadLocalTranscription();
    const localFile = local && local.notes.length > 0 ? [{
      name: local.name,
      url: local.audioDataUrl || "",
      id: "__local__",
      notes: local.notes,
      midi_base64: local.midi_base64,
    } as LibFile] : [];

    listLibrary().then((lib) => {
      setFiles([...localFile, ...lib]);
      if (!selectedIdProp && localFile.length > 0 && lib.length === 0) {
        setSelectedIdLocal("__local__");
        onTrackSelected?.("__local__");
      }
    }).catch(() => {
      setFiles(localFile);
      if (!selectedIdProp && localFile.length > 0) {
        setSelectedIdLocal("__local__");
        onTrackSelected?.("__local__");
      }
    });
  }, []);

  useEffect(() => {
    if (initialTrackId && files.length > 0) {
      setSelectedIdLocal(initialTrackId);
      onTrackSelected?.(initialTrackId);
    }
  }, [initialTrackId, files, onTrackSelected]);

  const selected = files.find((f) => f.id === selectedId);
  const hasNotes = (selected?.notes?.length ?? 0) > 0;
  const isThisPlaying = playing === selectedId;

  const stopMidi = useCallback(() => {
    if (midiIntervalRef.current) {
      clearInterval(midiIntervalRef.current);
      midiIntervalRef.current = null;
    }
    setMidiTime(0);
    midiOffsetRef.current = 0;
  }, []);

  const playSource = useCallback(async (source: PlaybackSource) => {
    if (!selected) return;
    sharedStop();
    stopMidi();
    setUseFallbackTimer(false);

    if (source === "original") {
      if (selected.url) play(selectedId, selected.url);
      return;
    }

    if (source === "midi" || source === "sheet-music") {
      const cachedUrl = source === "midi" ? midiWavUrl : sheetWavUrl;
      if (cachedUrl) {
        play(selectedId, cachedUrl);
        return;
      }

      setSynthLoading(true);
      try {
        let wav_base64: string;
        if (source === "sheet-music" && musicXml) {
          const converted = await synthMusicXml(btoa(musicXml));
          wav_base64 = converted.wav_base64;
        } else if (selected.midi_base64) {
          const synth = await synthAudio(selected.midi_base64);
          wav_base64 = synth.wav_base64;
        } else {
          setSynthLoading(false);
          return;
        }
        const bytes = Uint8Array.from(atob(wav_base64), (c) => c.charCodeAt(0));
        const blob = new Blob([bytes], { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        if (source === "midi") setMidiWavUrl(url);
        else setSheetWavUrl(url);
        play(selectedId, url);
      } catch {
        setUseFallbackTimer(true);
        const notes = selected.notes ?? [];
        const maxEnd = notes.length > 0 ? Math.max(...notes.map((n) => n.end)) : 0;
        setMidiDuration(maxEnd);
        midiStartRef.current = performance.now();
        midiOffsetRef.current = 0;
        setMidiTime(0);
        midiIntervalRef.current = setInterval(() => {
          const elapsed = (performance.now() - midiStartRef.current) / 1000;
          setMidiTime(midiOffsetRef.current + elapsed);
        }, 50);
      } finally {
        setSynthLoading(false);
      }
    }
  }, [selected, selectedId, midiWavUrl, sheetWavUrl, musicXml, play, sharedStop, stopMidi]);

  const handleStop = useCallback(() => {
    stopMidi();
    sharedStop();
  }, [stopMidi, sharedStop]);

  const handlePlay = useCallback(() => {
    if (isThisPlaying) {
      handleStop();
    } else {
      playSource(playbackSource);
    }
  }, [isThisPlaying, playbackSource, playSource, handleStop]);

  const handleSeek = useCallback((pct: number) => {
    const a = audioRef.current;
    if (a && duration > 0 && pct >= 0 && pct <= 1) a.currentTime = pct * duration;
  }, [audioRef, duration]);

  useEffect(() => {
    return () => {
      if (midiIntervalRef.current) clearInterval(midiIntervalRef.current);
      if (midiWavUrl) URL.revokeObjectURL(midiWavUrl);
      if (sheetWavUrl) URL.revokeObjectURL(sheetWavUrl);
    };
  }, []);

  useEffect(() => {
    if (onStopRef) {
      onStopRef.current = handleStop;
      return () => { onStopRef.current = null; };
    }
  }, [onStopRef, handleStop]);

  useEffect(() => {
    if (playing !== selectedId) {
      stopMidi();
    }
  }, [playing, selectedId, stopMidi]);

  // Reset when track changes
  useEffect(() => {
    if (midiWavUrl) URL.revokeObjectURL(midiWavUrl);
    if (sheetWavUrl) URL.revokeObjectURL(sheetWavUrl);
    setMidiWavUrl(null);
    setSheetWavUrl(null);
    setMusicXml("");
    stopMidi();
    setPlaybackSource("midi");
  }, [selectedId]);

  // Load MusicXML for sheet-music viz mode or playback source
  useEffect(() => {
    if ((mode === "sheet-music" || playbackSource === "sheet-music") && selected?.midi_base64 && !musicXml) {
      // Use MusicXML from library track if available, otherwise convert
      if (selected.musicxml) {
        setMusicXml(selected.musicxml);
      } else {
        setSheetMusicLoading(true);
        convertMusicFormat(selected.midi_base64, "midi", "musicxml")
          .then((converted) => setMusicXml(atob(converted.data_base64)))
          .catch(() => setMusicXml(""))
          .finally(() => setSheetMusicLoading(false));
      }
    }
  }, [mode, playbackSource, selected, musicXml]);

  // Calculate MIDI duration
  useEffect(() => {
    if (selected?.notes && selected.notes.length > 0) {
      const maxEnd = Math.max(...selected.notes.map((n) => n.end));
      setMidiDuration(maxEnd);
    }
  }, [selected]);

  const vizTime = useFallbackTimer ? midiTime : currentTime;
  const totalDuration = duration || midiDuration;
  const currentPct = totalDuration > 0 ? (vizTime / totalDuration) * 100 : 0;

  const tracksWithNotes = files.filter((f) => (f.notes?.length ?? 0) > 0);
  const showTrackPicker = tracksWithNotes.length > 1;

  return (
    <div className="card">
      <h3 className="card-title"><span className="glyph">◈</span> Visualize</h3>

      {tracksWithNotes.length === 0 ? (
        <div className="empty">
          No transcribed tracks in your library — transcribe one first.
        </div>
      ) : showTrackPicker ? (
        <>
          <div className="section-label">Select a transcribed track</div>
          <select
            className="sel"
            value={selectedId}
            onChange={(e) => {
              handleStop();
              setSelectedIdLocal(e.target.value);
              onTrackSelected?.(e.target.value);
              setMode("piano-roll");
            }}
            style={{ width: "100%", marginBottom: "var(--s-3)" }}
          >
            <option value="">-- Pick a track --</option>
            {tracksWithNotes.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </>
      ) : null}

      {selected && (
        <>
          <div className="section-label">Playback source</div>
          <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-3)", flexWrap: "wrap" }}>
            {selected.url && (
              <button
                className={`chip${playbackSource === "original" ? "" : " ghost"}`}
                onClick={() => { handleStop(); setPlaybackSource("original"); }}
              >
                Original
              </button>
            )}
            {hasNotes && (
              <button
                className={`chip${playbackSource === "midi" ? "" : " ghost"}`}
                onClick={() => { handleStop(); setPlaybackSource("midi"); }}
              >
                MIDI
              </button>
            )}
            {hasNotes && (musicXml || selected?.musicxml) && (
              <button
                className={`chip${playbackSource === "sheet-music" ? "" : " ghost"}`}
                onClick={() => { handleStop(); setPlaybackSource("sheet-music"); }}
              >
                Sheet Music
              </button>
            )}
          </div>

          <div className="section-label">Playback</div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", marginBottom: "var(--s-1)" }}>
            <button className="icon-btn" onClick={handlePlay} disabled={synthLoading}>
              {synthLoading ? "◌" : isThisPlaying ? "⏸" : "▶"}
            </button>
            <div
              className="pb-track"
              style={{ flex: 1, height: 6 }}
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const pct = (e.clientX - rect.left) / rect.width;
                handleSeek(Math.max(0, Math.min(1, pct)));
              }}
            >
              <div className="pb-fill" style={{ width: `${currentPct}%` }} />
            </div>
            <span className="muted" style={{ fontFamily: "monospace", fontSize: "var(--fs-xs)" }}>
              {formatTime(vizTime)} / {formatTime(totalDuration || 0)}
            </span>
          </div>
          <Visualizer audioRef={audioRef} />

          <div className="section-label">Visualization</div>
          <div style={{ display: "flex", gap: "var(--s-1)", marginBottom: "var(--s-3)", flexWrap: "wrap" }}>
            {VIZ_MODES.filter((m) => (hasNotes || m.id === "spectrogram") && (m.id !== "sheet-music" || musicXml || selected?.musicxml)).map((m) => (
              <button
                key={m.id}
                className={`chip${mode === m.id ? "" : " ghost"}`}
                onClick={() => setMode(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>

          {mode === "piano-roll" && hasNotes && (
            <PianoRoll notes={selected.notes!} playheadTime={vizTime} bpm={120} />
          )}

          {mode === "spectrogram" && selected.url && (
            <Spectrogram url={selected.url} />
          )}

          {mode === "chroma" && hasNotes && (
            <ChromaHeatmap notes={selected.notes!} />
          )}

          {mode === "tonnetz" && hasNotes && (
            <Tonnetz notes={selected.notes!} />
          )}

          {mode === "sheet-music" && (
            <>
              {musicXml ? (
                <SheetMusic musicXml={musicXml} />
              ) : sheetMusicLoading ? (
                <div style={{ textAlign: "center", padding: "var(--s-4)", color: "var(--muted)", fontSize: "var(--fs-sm)" }}>
                  Loading sheet music…
                </div>
              ) : selected?.midi_base64 ? (
                <div style={{ textAlign: "center", padding: "var(--s-4)", color: "var(--muted)", fontSize: "var(--fs-sm)" }}>
                  No MIDI data available for sheet music.
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "var(--s-4)", color: "var(--muted)", fontSize: "var(--fs-sm)" }}>
                  Select a track with MIDI data.
                </div>
              )}
            </>
          )}
        </>
      )}

    </div>
  );
}
