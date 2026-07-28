"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTransport, type PlaybackSource } from "@/hooks/useTransport";
import {
  transcribeAudio,
  convertMusicFormat,
  analyzeAudio,
  saveTranscription,
  audioFmtFromName,
  type TranscribeResult,
  type LibFile,
} from "@/lib/music";
import { useSharedAudio } from "@/lib/audio-context";
import PianoRoll from "@/components/PianoRoll";
import Spectrogram from "@/components/Spectrogram";
import ChromaHeatmap from "@/components/ChromaHeatmap";
import Tonnetz from "@/components/Tonnetz";
import SheetMusic from "@/components/SheetMusic";
import Analysis from "@/components/analyze";

type ProcessStep = "idle" | "transcribing" | "sheet-music" | "analyzing" | "done";
type WorkspaceTab = "overview" | "analysis";

export default function TrackWorkspace({
  file,
  signedIn,
  onTrackUpdated,
  autoProcess,
}: {
  file: LibFile | null;
  signedIn: boolean;
  onTrackUpdated?: () => void;
  autoProcess?: boolean;
}) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [processStep, setProcessStep] = useState<ProcessStep>("idle");
  const [processError, setProcessError] = useState("");
  const [musicXml, setMusicXml] = useState(file?.musicxml ?? "");
  const [analysis, setAnalysis] = useState(file?.analysis ?? null);
  const processedRef = useRef(new Set<string>());
  const { stop: stopAudio } = useSharedAudio();

  const transport = useTransport(file?.id ?? null, file?.midi_base64);

  const hasNotes = Boolean(file?.notes && file.notes.length > 0);
  const hasMidi = Boolean(file?.midi_base64);
  const hasSheetMusic = Boolean(file?.musicxml || musicXml);
  const hasAnalysis = Boolean(analysis);
  const isProcessing = processStep !== "idle" && processStep !== "done";
  const allDone = hasNotes && hasSheetMusic && hasAnalysis;

  // Reset state when file changes
  useEffect(() => {
    setMusicXml(file?.musicxml ?? "");
    setAnalysis(file?.analysis ?? null);
    setProcessStep("idle");
    setProcessError("");
    setActiveTab("overview");
    transport.stop();
  }, [file?.id]);

  // Auto-process pipeline
  useEffect(() => {
    if (autoProcess && file && !allDone && !isProcessing && !processedRef.current.has(file.id)) {
      processedRef.current.add(file.id);
      processAll();
    }
  }, [autoProcess, file?.id, allDone]);

  async function processAll() {
    if (!file || isProcessing) return;
    setProcessError("");
    try {
      // Step 1: Transcribe
      if (!hasNotes) {
        setProcessStep("transcribing");
        const result: TranscribeResult = await transcribeAudio(undefined, audioFmtFromName(file.name), file.id);
        file.notes = result.notes;
        file.midi_base64 = result.midi_base64;
        if (result.analysis) {
          setAnalysis(result.analysis);
          file.analysis = result.analysis;
        }
      }

      // Step 2: Sheet Music
      if (!hasSheetMusic && file.midi_base64) {
        setProcessStep("sheet-music");
        const res = await convertMusicFormat(file.midi_base64, "midi", "musicxml");
        setMusicXml(res.data_base64);
        file.musicxml = res.data_base64;
      }

      // Step 3: Analyze
      if (!hasAnalysis && file.midi_base64) {
        setProcessStep("analyzing");
        const result = await analyzeAudio(file.midi_base64);
        setAnalysis(result ?? null);
        file.analysis = result;
      }

      setProcessStep("done");
      if (signedIn && file.id) {
        try {
          await saveTranscription(file.id, file.notes ?? [], file.midi_base64, analysis ?? file.analysis);
        } catch {}
      }
      onTrackUpdated?.();
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : "Processing failed");
      setProcessStep("idle");
    }
  }

  function formatTime(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  if (!file) return null;

  const sources: { id: PlaybackSource; label: string; enabled: boolean }[] = [
    { id: "original", label: "Original", enabled: true },
    { id: "midi", label: "MIDI", enabled: hasMidi },
    { id: "synth", label: "Synth", enabled: hasMidi },
  ];

  const representations: { label: string; purpose: string; available: boolean; content: React.ReactNode }[] = [
    {
      label: "Waveform",
      purpose: "Playback navigation",
      available: Boolean(file.url),
      content: <Spectrogram url={file.url!} height={100} />,
    },
    {
      label: "Piano Roll",
      purpose: "Timing, pitch, density",
      available: hasNotes,
      content: hasNotes ? <PianoRoll notes={file.notes!} bpm={analysis?.tempo?.bpm ?? 120} playheadTime={transport.currentTime} /> : null,
    },
    {
      label: "Sheet Music",
      purpose: "Notation, performance",
      available: hasSheetMusic,
      content: hasSheetMusic ? <SheetMusic musicXml={musicXml} /> : null,
    },
    {
      label: "Chroma",
      purpose: "Harmony, key detection",
      available: hasNotes,
      content: hasNotes ? <ChromaHeatmap notes={file.notes!} /> : null,
    },
    {
      label: "Tonnetz",
      purpose: "Harmonic relationships",
      available: hasNotes,
      content: hasNotes ? <Tonnetz notes={file.notes!} /> : null,
    },
  ];

  const insightSummary = analysis ? generateInsightSummary(analysis) : null;

  return (
    <div style={{ padding: "var(--s-5) var(--s-6)", overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div className="ws-header">
        <div className="ws-title">{file.name}</div>
        <div className="ws-status">
          {allDone && <span className="badge done"><span className="badge-dot" /> Processed</span>}
          {isProcessing && <span className="badge processing"><span className="badge-dot" /> Processing...</span>}
          {!allDone && !isProcessing && <span className="badge">Not processed</span>}
        </div>
      </div>

      {/* Processing Pipeline */}
      {(!allDone || isProcessing) && (
        <div className="pipeline">
          <PipelineStep step="transcribing" label="Transcribe" current={processStep} />
          <span className="pipeline-arrow">→</span>
          <PipelineStep step="sheet-music" label="Sheet" current={processStep} />
          <span className="pipeline-arrow">→</span>
          <PipelineStep step="analyzing" label="Analyze" current={processStep} />
          {!isProcessing && processStep === "idle" && (
            <div className="pipeline-action">
              <button className="btn btn-primary btn-sm" onClick={processAll}>
                Process Track
              </button>
            </div>
          )}
        </div>
      )}

      {processError && (
        <div style={{ padding: "var(--s-3)", background: "var(--danger-soft)", color: "var(--danger)", borderRadius: "var(--r-md)", marginBottom: "var(--s-4)", fontSize: "var(--fs-sm)" }}>
          {processError}
        </div>
      )}

      {/* Transport */}
      <div className="transport">
        <button
          className="transport-play"
          onClick={transport.toggle}
          disabled={!transport.duration && transport.source === "original"}
        >
          {transport.isPlaying ? "⏸" : "▶"}
        </button>

        <div className="transport-timeline">
          <div
            className="transport-track"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              if (rect.width === 0 || !transport.duration) return;
              const pct = (e.clientX - rect.left) / rect.width;
              transport.seek(pct * transport.duration);
            }}
          >
            <div
              className="transport-fill"
              style={{ width: `${transport.duration > 0 ? (transport.currentTime / transport.duration) * 100 : 0}%` }}
            />
          </div>
          <div className="transport-times">
            <span>{formatTime(transport.currentTime)}</span>
            <span>{formatTime(transport.duration)}</span>
          </div>
        </div>

        <div className="transport-sources">
          {sources.map((s) => (
            <button
              key={s.id}
              className={`transport-src${transport.source === s.id ? " active" : ""}`}
              onClick={() => transport.setSource(s.id)}
              disabled={!s.enabled || transport.isLoading}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Switcher */}
      <div style={{ display: "flex", gap: "var(--s-1)", marginBottom: "var(--s-5)" }}>
        <button
          className={`btn btn-sm${activeTab === "overview" ? " btn-primary" : " btn-ghost"}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        <button
          className={`btn btn-sm${activeTab === "analysis" ? " btn-primary" : " btn-ghost"}`}
          onClick={() => setActiveTab("analysis")}
          disabled={!hasAnalysis}
        >
          Analysis
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <>
          {/* Analysis Summary (embedded) */}
          {insightSummary && (
            <div className="analysis-summary fade-in">
              <div className="analysis-blurb">{insightSummary.blurb}</div>
              <div className="analysis-highlights">
                {insightSummary.highlights.map((h, i) => (
                  <span key={i} className={`highlight ${h.type}`}>{h.text}</span>
                ))}
              </div>
            </div>
          )}

          {/* Quick Stats */}
          {analysis && (
            <div className="stat-row fade-in">
              {analysis.key && (
                <div className="stat-card">
                  <div className="stat-label">Key</div>
                  <div className="stat-value">{analysis.key.tonic} {analysis.key.mode}</div>
                  <div className="stat-conf"><div className="stat-conf-fill" style={{ width: `${Math.round(analysis.key.confidence * 100)}%` }} /></div>
                </div>
              )}
              {analysis.tempo && (
                <div className="stat-card">
                  <div className="stat-label">Tempo</div>
                  <div className="stat-value">{Math.round(analysis.tempo.bpm)} BPM</div>
                  <div className="stat-conf"><div className="stat-conf-fill" style={{ width: `${Math.round(analysis.tempo.confidence * 100)}%` }} /></div>
                </div>
              )}
              {analysis.time_signature && (
                <div className="stat-card">
                  <div className="stat-label">Time</div>
                  <div className="stat-value">{analysis.time_signature.numerator}/{analysis.time_signature.denominator}</div>
                  <div className="stat-conf"><div className="stat-conf-fill" style={{ width: `${Math.round(analysis.time_signature.confidence * 100)}%` }} /></div>
                </div>
              )}
              <div className="stat-card">
                <div className="stat-label">Notes</div>
                <div className="stat-value">{file.notes?.length ?? 0}</div>
              </div>
            </div>
          )}

          {/* Representations Grid */}
          <div className="section">
            <div className="section-title">Representations</div>
            <div className="repr-grid">
              {representations.map((r) => (
                <div key={r.label} className={`repr-card${!r.available ? " empty" : ""}`}>
                  <div className="repr-card-header">
                    <span className="repr-card-label">{r.label}</span>
                    <span className="repr-card-purpose">{r.purpose}</span>
                  </div>
                  <div className={`repr-card-body${r.label === "Sheet Music" ? " full" : ""}`}>
                    {r.available ? r.content : <span className="muted">Not available</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chord Timeline (embedded) */}
          {analysis?.chords && analysis.chords.length > 0 && (
            <div className="section fade-in">
              <div className="section-title">Chord Timeline</div>
              <ChordTimeline chords={analysis.chords} modulations={analysis.modulations} notes={file.notes ?? []} />
            </div>
          )}

          {/* Roman Numerals (embedded) */}
          {analysis?.roman_numerals && analysis.roman_numerals.length > 0 && (
            <div className="section fade-in">
              <div className="section-title">Harmonic Progression</div>
              <div className="rn-chips">
                {analysis.roman_numerals.map((rn, i) => {
                  const cadMatch = analysis.cadences?.find((c) => Math.abs(c.position - rn.start) < 0.5);
                  return (
                    <span key={i} className={`rn-chip${cadMatch ? " cadence" : ""}`}>
                      {rn.figure}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Analysis Tab */}
      {activeTab === "analysis" && hasAnalysis && (
        <Analysis analysis={analysis} notes={file.notes ?? []} audioName={file.name} numNotes={file.notes?.length ?? 0} />
      )}
    </div>
  );
}

// ── Pipeline Step ────────────────────────────────────────────────────────────

function PipelineStep({ step, label, current }: { step: ProcessStep; label: string; current: ProcessStep }) {
  const steps: ProcessStep[] = ["transcribing", "sheet-music", "analyzing"];
  const currentIdx = steps.indexOf(current);
  const stepIdx = steps.indexOf(step);
  const isDone = currentIdx > stepIdx || current === "done";
  const isActive = current === step;

  return (
    <div className={`pipeline-step${isActive ? " active" : ""}${isDone ? " done" : ""}`}>
      <div className="pipeline-dot">
        {isDone ? "✓" : isActive ? "" : ""}
      </div>
      {label}
    </div>
  );
}

// ── Chord Timeline ────────────────────────────────────────────────────────────

function ChordTimeline({
  chords,
  modulations,
  notes,
}: {
  chords: { root: string; quality: string; start: number; end: number }[];
  modulations?: { from_key: string; to_key: string; position: number }[];
  notes: { pitch: number; start: number; end: number; velocity: number }[];
}) {
  const totalDuration = notes.length > 0 ? Math.max(...notes.map((n) => n.end)) : 0;
  if (totalDuration === 0) return null;

  return (
    <>
      <div className="chord-timeline">
        {chords.map((c, i) => {
          const left = (c.start / totalDuration) * 100;
          const width = ((c.end - c.start) / totalDuration) * 100;
          const isMinor = c.quality === "m";
          const label = isMinor ? `${c.root}m` : c.root;
          return (
            <div
              key={i}
              className={`chord-seg ${isMinor ? "minor" : "major"}`}
              style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
              title={`${label} (${Math.floor(c.start / 60)}:${Math.floor(c.start % 60).toString().padStart(2, "0")} – ${Math.floor(c.end / 60)}:${Math.floor(c.end % 60).toString().padStart(2, "0")})`}
            >
              {width > 4 && label}
            </div>
          );
        })}
        {modulations?.map((m, i) => (
          <div
            key={`mod-${i}`}
            className="chord-mod-marker"
            style={{ left: `${(m.position / totalDuration) * 100}%` }}
            title={`${m.from_key} → ${m.to_key}`}
          />
        ))}
      </div>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
        {chords.length} chord segments · {Math.floor(totalDuration / 60)}:{Math.floor(totalDuration % 60).toString().padStart(2, "0")} duration
        {modulations && modulations.length > 0 && ` · ${modulations.length} key change${modulations.length > 1 ? "s" : ""}`}
      </p>
    </>
  );
}

// ── Insight Summary Generator ────────────────────────────────────────────────

function generateInsightSummary(analysis: NonNullable<TranscribeResult["analysis"]>): {
  blurb: string;
  highlights: { text: string; type: string }[];
} {
  const keyName = `${analysis.key.tonic} ${analysis.key.mode}`;
  const bpm = analysis.tempo ? Math.round(analysis.tempo.bpm) : null;
  const highlights: { text: string; type: string }[] = [];

  // Generate blurb
  let blurb = `A piece in ${keyName}`;
  if (bpm) {
    if (bpm < 80) blurb += ` with a slow tempo`;
    else if (bpm < 120) blurb += ` at a moderate tempo`;
    else if (bpm < 160) blurb += ` with an upbeat tempo`;
    else blurb += ` at a fast tempo`;
  }
  blurb += ".";

  // Key confidence
  const keyConf = Math.round(analysis.key.confidence * 100);
  if (keyConf >= 80) highlights.push({ text: `Strong ${keyName} tonality`, type: "" });
  else if (keyConf >= 50) highlights.push({ text: `Likely ${keyName}`, type: "" });
  else highlights.push({ text: `Ambiguous key`, type: "warm" });

  // Tempo
  if (bpm) highlights.push({ text: `${bpm} BPM`, type: "" });

  // Cadences
  if (analysis.cadences && analysis.cadences.length > 0) {
    const types = analysis.cadences.map((c) => c.type);
    const dominant = types.sort((a, b) => types.filter((v) => v === b).length - types.filter((v) => v === a).length)[0];
    if (dominant) highlights.push({ text: `${dominant} cadences`, type: "warm" });
  }

  // Modulations
  if (analysis.modulations && analysis.modulations.length > 0) {
    highlights.push({ text: `${analysis.modulations.length} key change${analysis.modulations.length > 1 ? "s" : ""}`, type: "warm" });
  }

  // Rhythm
  if (analysis.rhythm) {
    if (analysis.rhythm.syncopation_ratio > 0.3) highlights.push({ text: "Syncopated", type: "" });
    if (analysis.rhythm.rhythmic_density > 8) highlights.push({ text: "Dense rhythm", type: "" });
  }

  return { blurb, highlights };
}
