"use client";

import RepresentationLane from "./RepresentationLane";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport } = useWorkspace();
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  const byKind = new Map(workspace.representations.map((item) => [item.kind, item]));
  const waveform = byKind.get("waveform");
  const score = byKind.get("score");
  const pianoRoll = byKind.get("piano_roll");
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);

  if (workspace.isLoadingWork) return <main className="piece-desk"><div className="piece-loading" role="status">Opening your piece…</div></main>;

  if (!waveform && !score && !pianoRoll) {
    return (
      <main className="piece-desk piece-empty">
        <p className="piece-eyebrow">Your library is empty</p>
        <h1>Start with a recording.</h1>
        <p>Upload one audio file. We will preserve the original, create a playable transcription, and derive views you can inspect together.</p>
        <button className="btn btn-primary" onClick={requestImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import…"}</button>
        <small>WAV, MP3, M4A, FLAC, OGG, or AAC · up to 4 MB</small>
      </main>
    );
  }

  return (
    <main className="piece-desk">
      <header className="piece-desk-heading">
        <div>
          <p className="piece-eyebrow">Listening workspace</p>
          <h1>{activeWork?.title ?? "Untitled piece"}</h1>
          <p>Use the transport once; every view follows the same playback position.</p>
        </div>
        <button type="button" className="btn" onClick={requestImport}>Import another piece</button>
      </header>

      {waveform && <section className="piece-audio-view" aria-labelledby="original-audio-title"><div className="piece-section-heading"><div><p className="piece-eyebrow">Original recording</p><h2 id="original-audio-title">Audio timeline</h2></div><span>{waveform.sourceLabel}</span></div><RepresentationLane kind={waveform.kind} label="Audio timeline" sourceLabel={waveform.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader audioUrl={waveform.audioUrl} /></section>}

      <div className="piece-views-grid">
        {pianoRoll && <section aria-labelledby="performance-view-title"><div className="piece-section-heading"><div><p className="piece-eyebrow">Performance transcription</p><h2 id="performance-view-title">Piano roll</h2></div><span>{pianoRoll.sourceLabel}</span></div><RepresentationLane kind={pianoRoll.kind} label="Piano roll" sourceLabel={pianoRoll.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader workspaceNotes={pianoRoll.notes} /></section>}
        {score && <section aria-labelledby="score-view-title"><div className="piece-section-heading"><div><p className="piece-eyebrow">Notation draft</p><h2 id="score-view-title">Score</h2></div><span>Review by ear</span></div><RepresentationLane kind={score.kind} label="Score" sourceLabel={score.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader musicxml={score.musicxml} /></section>}
      </div>

      <section className="piece-analysis" aria-labelledby="analysis-title"><div className="piece-section-heading"><div><p className="piece-eyebrow">Analysis</p><h2 id="analysis-title">What this transcription suggests</h2></div><span>Derived from MIDI; treat as evidence, not fact.</span></div><AnalysisSummary onSeek={seek} bpm={timeline.bpm} /></section>
    </main>
  );
}

function AnalysisSummary({ onSeek, bpm }: { onSeek: (seconds: number) => void; bpm: number }) {
  const { workspace } = useWorkspace();
  const primary = workspace.insights.filter((item) => ["key", "tempo", "time_signature"].includes(item.kind));
  const chords = workspace.insights.filter((item) => item.kind === "chord").slice(0, 12);
  const observations = workspace.insights.filter((item) => !["key", "tempo", "time_signature", "chord"].includes(item.kind)).slice(0, 8);
  const goTo = (item: (typeof workspace.insights)[number]) => {
    const seconds = item.span.start_seconds ?? (typeof item.span.start_beat === "number" && bpm > 0 ? item.span.start_beat * 60 / bpm : 0);
    onSeek(seconds);
  };
  if (!workspace.insights.length) return <p className="analysis-empty">Analysis is still being prepared for this transcription.</p>;
  return <div className="analysis-content"><div className="analysis-facts">{primary.map((item) => <div key={item.id}><span>{item.kind.replaceAll("_", " ")}</span><strong>{item.claim.replace(/^[^:]+:\s*/, "")}</strong><small>{Math.round(item.confidence * 100)}% confidence</small></div>)}</div>{chords.length > 0 && <div className="analysis-block"><h3>Harmonic path</h3><div className="rn-chips">{chords.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>{item.claim}</button>)}</div></div>}{observations.length > 0 && <div className="analysis-block"><h3>Observations</h3>{observations.map((item) => <button type="button" className="analysis-observation" key={item.id} onClick={() => goTo(item)}><span>{item.claim}</span><small>{Math.round(item.confidence * 100)}% confidence</small></button>)}</div>}</div>;
}
