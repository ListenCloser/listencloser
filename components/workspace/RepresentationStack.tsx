"use client";

import { useEffect, useState } from "react";
import RepresentationLane from "./RepresentationLane";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";

type View = "listen" | "piano_roll" | "score" | "analysis";

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport } = useWorkspace();
  const { seek, pause, play, setActiveSource, transport } = useTransport();
  const { timeline } = useTimeline();
  const byKind = new Map(workspace.representations.map((item) => [item.kind, item]));
  const waveform = byKind.get("waveform");
  const score = byKind.get("score");
  const pianoRoll = byKind.get("piano_roll");
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);
  const available: View[] = [waveform && "listen", pianoRoll && "piano_roll", score && "score", workspace.insights.length && "analysis"].filter(Boolean) as View[];
  const [activeView, setActiveView] = useState<View>(available[0] ?? "listen");

  useEffect(() => {
    if (!available.includes(activeView)) setActiveView(available[0] ?? "listen");
  }, [activeView, available]);

  if (workspace.isLoadingWork) return <main className="piece-desk"><div className="piece-loading" role="status">Opening your piece…</div></main>;
  if (!available.length) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;

  const title: Record<View, string> = { listen: "Listen", piano_roll: "Piano roll", score: "Score", analysis: "Analysis" };
  const subtitle: Record<View, string> = { listen: "Original and transcription playback", piano_roll: "Performance timing and note events", score: "Quantized notation draft", analysis: "Claims linked to the timeline" };
  const playView = () => {
    if (transport.isPlaying) { pause(); return; }
    const transcription = transport.sources.find((source) => source.label === "Transcription playback");
    if (activeView !== "listen" && transcription && transcription.id !== transport.activeSource?.id) {
      setActiveSource(transcription);
      window.setTimeout(play, 0);
      return;
    }
    play();
  };
  return <main className="piece-desk">
    <header className="piece-desk-heading"><div><p className="piece-eyebrow">Listening workspace</p><h1>{activeWork?.title ?? "Untitled piece"}</h1><p>{subtitle[activeView]}. The transport remains the source of truth in every view.</p></div><button type="button" className="btn" onClick={requestImport}>Import another piece</button></header>
    <div className="piece-view-tabs" role="tablist" aria-label="Workspace views">{available.map((view) => <button key={view} type="button" role="tab" aria-selected={activeView === view} className={activeView === view ? "active" : ""} onClick={() => setActiveView(view)}><strong>{title[view]}</strong><span>{subtitle[view]}</span></button>)}</div>
    <section className="piece-active-view" aria-labelledby="active-view-title"><div className="piece-section-heading"><div><p className="piece-eyebrow">{subtitle[activeView]}</p><h2 id="active-view-title">{title[activeView]}</h2></div>{activeView !== "analysis" && <button className="btn piece-view-play" type="button" onClick={playView} disabled={!transport.activeSource}>{transport.isPlaying ? "Pause playback" : activeView === "listen" ? "Play selected source" : "Play transcription"}</button>}</div>
      {activeView === "listen" && waveform && <RepresentationLane kind="waveform" label="Audio timeline" sourceLabel={waveform.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader audioUrl={waveform.audioUrl} />}
      {activeView === "piano_roll" && pianoRoll && <RepresentationLane kind="piano_roll" label="Piano roll" sourceLabel={pianoRoll.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader workspaceNotes={pianoRoll.notes} />}
      {activeView === "score" && score && <RepresentationLane kind="score" label="Score" sourceLabel={score.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader musicxml={score.musicxml} />}
      {activeView === "analysis" && <AnalysisSummary onSeek={seek} bpm={timeline.bpm} />}
    </section>
  </main>;
}

function EmptyDesk({ signedIn, canImport, onImport }: { signedIn: boolean; canImport: boolean; onImport: () => void }) { return <main className="piece-desk piece-empty"><p className="piece-eyebrow">Your library is empty</p><h1>Start with a recording.</h1><p>Upload one audio file. We will preserve the original, create a playable transcription, and derive views you can inspect together.</p><button className="btn btn-primary" onClick={onImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import…"}</button><small>WAV, MP3, M4A, FLAC, OGG, or AAC · up to 4 MB</small></main>; }

function AnalysisSummary({ onSeek, bpm }: { onSeek: (seconds: number) => void; bpm: number }) {
  const { workspace } = useWorkspace();
  const confident = workspace.insights.filter((item) => item.confidence >= 0.5);
  const primary = confident.filter((item) => ["key", "tempo", "time_signature", "audio_tempo"].includes(item.kind));
  const chords = confident.filter((item) => item.kind === "chord").slice(0, 12);
  const sections = confident.filter((item) => item.kind === "section").slice(0, 12);
  const observations = confident.filter((item) => !["key", "tempo", "time_signature", "audio_tempo", "chord", "section"].includes(item.kind));
  const goTo = (item: (typeof workspace.insights)[number]) => onSeek(item.span.start_seconds ?? (typeof item.span.start_beat === "number" && bpm > 0 ? item.span.start_beat * 60 / bpm : 0));
  if (!workspace.insights.length) return <p className="analysis-empty">Analysis is still being prepared for this transcription.</p>;
  const filteredCount = workspace.insights.length - confident.length;
  return <div className="analysis-content"><div className="analysis-facts">{primary.map((item) => <div key={item.id}><span>{item.kind.replaceAll("_", " ")}</span><strong>{item.claim.replace(/^[^:]+:\s*/, "")}</strong></div>)}</div>{sections.length > 0 && <div className="analysis-block"><h3>Form</h3><div className="rn-chips">{sections.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>{item.claim}</button>)}</div></div>}{chords.length > 0 && <div className="analysis-block"><h3>Harmonic path</h3><div className="rn-chips">{chords.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>{item.claim}</button>)}</div></div>}{observations.length > 0 && <div className="analysis-block"><h3>Observations</h3>{observations.map((item) => <button type="button" className="analysis-observation" key={item.id} onClick={() => goTo(item)}><span>{item.claim}</span><small>{Math.round(item.confidence * 100)}% confidence</small></button>)}</div>}{filteredCount > 0 && <p className="analysis-filtered-notice">{filteredCount} low-confidence claim{filteredCount !== 1 ? "s" : ""} hidden.</p>}</div>;
}
