"use client";

import { useEffect, useState, type ReactNode } from "react";
import RepresentationLane from "./RepresentationLane";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { presentableTitle } from "@/lib/format";
import { deriveAvailability } from "@/lib/representation-availability";

type View = "listen" | "piano_roll" | "score" | "analysis";

const VIEWS: Record<View, { title: string; description: string }> = {
  listen: {
    title: "Listen",
    description: "Hear your recording and its transcription — choose what you're hearing in the transport.",
  },
  piano_roll: {
    title: "Piano roll",
    description: "Every detected note with its timing and pitch.",
  },
  score: {
    title: "Score",
    description: "Score playback follows the written timing.",
  },
  analysis: {
    title: "Analysis",
    description: "A musical summary of the transcription. Select an item to hear that moment.",
  },
};

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport } = useWorkspace();
  const { seek, transport } = useTransport();
  const { timeline } = useTimeline();
  const { byKind, analysis } = deriveAvailability(workspace.representations, workspace.insights.length);
  const waveform = byKind.get("waveform");
  const score = byKind.get("score");
  const pianoRoll = byKind.get("piano_roll");
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);
  const available: View[] = [waveform && "listen", pianoRoll && "piano_roll", score && "score", analysis && "analysis"].filter(Boolean) as View[];
  const [activeView, setActiveView] = useState<View>("listen");

  useEffect(() => {
    if (!available.includes(activeView)) {
      setActiveView(available.includes("listen") ? "listen" : (available[0] ?? "listen"));
    }
  }, [activeView, available]);

  if (workspace.isLoadingWork) {
    return (
      <main className="piece-desk">
        <div className="piece-loading" role="status">
          <span className="spinner" aria-hidden="true" />
          <div className="piece-loading-copy">
            <strong>Opening your music…</strong>
            <span>Loading the saved recording, transcription, and analysis.</span>
          </div>
        </div>
      </main>
    );
  }
  if (!available.length) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;

  const view = VIEWS[activeView];

  return <main className="piece-desk">
    <header className="piece-desk-heading">
      <div className="piece-desk-title">
        <h1 title={activeWork?.title}>{presentableTitle(activeWork?.title ?? "Untitled piece")}</h1>
        <p>{view.description}</p>
      </div>
      <button type="button" className="btn" onClick={requestImport}>Import another</button>
    </header>

    <div className="piece-view-tabs" role="tablist" aria-label="Workspace views">
      {available.map((key) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={activeView === key}
          className={activeView === key ? "active" : ""}
          onClick={() => setActiveView(key)}
        >
          {VIEWS[key].title}
        </button>
      ))}
    </div>

    <section className="piece-active-view" aria-label={view.title}>
      {activeView === "listen" && waveform && <RepresentationLane kind="waveform" label="Audio timeline" sourceLabel={transport.activeSource?.label ?? waveform.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader audioUrl={waveform.audioUrl} />}
      {activeView === "piano_roll" && pianoRoll && <RepresentationLane kind="piano_roll" label="Piano roll" sourceLabel={pianoRoll.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader workspaceNotes={pianoRoll.notes} />}
      {activeView === "score" && score && <RepresentationLane kind="score" label="Score" sourceLabel={score.sourceLabel} confidence={null} isExpanded onExpand={() => {}} hideHeader musicxml={score.musicxml} measureStarts={score.measureStarts} />}
      {activeView === "analysis" && <div className="piece-analysis"><AnalysisSummary onSeek={seek} bpm={timeline.bpm} /></div>}
    </section>
  </main>;
}

function EmptyDesk({ signedIn, canImport, onImport }: { signedIn: boolean; canImport: boolean; onImport: () => void }) {
  return (
    <main className="piece-desk piece-empty">
      <h1>Start with a recording.</h1>
      <p>Upload an audio file. We will keep the original, create a playable transcription, and give you a piano roll, score, and analysis to inspect together.</p>
      <button className="btn btn-primary" onClick={onImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import…"}</button>
      <small>WAV, MP3, M4A, FLAC, OGG, or AAC · up to 4 MB</small>
    </main>
  );
}

const NOT_DETECTED = "Not confidently detected";

export function AnalysisSummary({ onSeek, bpm }: { onSeek: (seconds: number) => void; bpm: number }) {
  const { workspace } = useWorkspace();
  const confident = workspace.insights.filter((item) => item.confidence != null && item.confidence >= 0.5);
  const claimValue = (item?: (typeof workspace.insights)[number]) => (item ? item.claim.replace(/^[^:]+:\s*/, "") : NOT_DETECTED);
  const keyFact = confident.find((item) => item.kind === "key");
  const tempoFact = confident.find((item) => item.kind === "audio_tempo") ?? confident.find((item) => item.kind === "tempo");
  const meterFact = confident.find((item) => item.kind === "time_signature");
  const factDefinitions = [
    { label: "Key", value: claimValue(keyFact) },
    { label: "Tempo", value: claimValue(tempoFact) },
    { label: "Time signature", value: claimValue(meterFact) },
  ];
  const presentFacts = factDefinitions.filter((fact) => fact.value !== NOT_DETECTED);
  const missingFacts = factDefinitions.filter((fact) => fact.value === NOT_DETECTED);
  const chords = confident.filter((item) => item.kind === "chord").slice(0, 12);
  const sections = confident.filter((item) => item.kind === "section").slice(0, 12);
  const observations = confident.filter((item) => !["key", "tempo", "time_signature", "audio_tempo", "chord", "section"].includes(item.kind));
  const goTo = (item: (typeof workspace.insights)[number]) => onSeek(item.span.start_seconds ?? (typeof item.span.start_beat === "number" && bpm > 0 ? item.span.start_beat * 60 / bpm : 0));
  if (!workspace.insights.length) return <p className="analysis-empty">Analysis is still being prepared for this transcription.</p>;
  const filteredCount = workspace.insights.length - confident.length;
  return (
    <div className="analysis-content">
      {presentFacts.length > 0 && (
        <div className="analysis-facts">
          {presentFacts.map((fact) => (
            <div key={fact.label}>
              <span>{fact.label}</span>
              <strong>{fact.value}</strong>
            </div>
          ))}
        </div>
      )}
      {missingFactsNote(presentFacts.length, missingFacts)}
      {sections.length > 0 && <div className="analysis-block"><h3>Form</h3><div className="rn-chips">{sections.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>{item.claim}</button>)}</div></div>}
      {chords.length > 0 && <div className="analysis-block"><h3>Harmonic path</h3><div className="rn-chips">{chords.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>{item.claim}</button>)}</div></div>}
      {observations.length > 0 && <div className="analysis-block"><h3>Observations</h3>{observations.map((item) => <button type="button" className="analysis-observation" key={item.id} onClick={() => goTo(item)}><span>{item.claim}</span></button>)}</div>}
      {presentFacts.length + sections.length + chords.length + observations.length === 0 && (
        <div className="analysis-unavailable">
          <strong>The automatic summary came back empty</strong>
          <span>We couldn't confidently identify the key, tempo, or form for this piece. The notes and structure are still available in the other views.</span>
        </div>
      )}
      {filteredCount > 0 && (
        <p className="analysis-filtered-notice">
          Some possible findings were too uncertain to show.
        </p>
      )}
    </div>
  );
}

function missingFactsNote(presentCount: number, missingFacts: { label: string; value: string }[]): ReactNode {
  if (presentCount === 0 || missingFacts.length === 0) return null;
  const names = missingFacts.map((fact) => fact.label.toLowerCase());
  return <p className="analysis-missing-note">The {names.join(" and ")} {names.length > 1 ? "weren't" : "wasn't"} detected confidently.</p>;
}
