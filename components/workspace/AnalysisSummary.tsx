"use client";

import type { ReactNode } from "react";
import { useWorkspace } from "@/lib/stores/workspace";

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