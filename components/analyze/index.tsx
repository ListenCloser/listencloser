"use client";

import type { TranscribeResult } from "@/lib/music";
import { computeNoteStats } from "@/lib/note-stats";
import { FLAT_NOTE_NAMES, SHARP_NOTE_NAMES } from "@/lib/notes";

type Props = {
  analysis: TranscribeResult["analysis"] | null | undefined;
  notes: TranscribeResult["notes"];
  audioName: string;
  numNotes: number;
};

function tonicToIndex(tonic: string): number {
  const s = SHARP_NOTE_NAMES.indexOf(tonic as (typeof SHARP_NOTE_NAMES)[number]);
  if (s !== -1) return s;
  return FLAT_NOTE_NAMES.indexOf(tonic as (typeof FLAT_NOTE_NAMES)[number]);
}

function getDiatonicChords(tonic: string, mode: string) {
  const rootIdx = tonicToIndex(tonic);
  if (rootIdx === -1) return [];
  const isMajor = mode === "major";
  const degrees = isMajor ? [0, 2, 4, 5, 7, 9, 11] : [0, 2, 3, 5, 7, 8, 10];
  const qualities = isMajor
    ? ["major", "minor", "minor", "major", "major", "minor", "dim"]
    : ["minor", "dim", "major", "minor", "minor", "major", "major"];
  return degrees.map((d, i) => {
    const idx = (rootIdx + d) % 12;
    const root = SHARP_NOTE_NAMES[idx];
    const q = qualities[i];
    const label = q === "major" ? root : `${root}${q === "dim" ? "dim" : "m"}`;
    return { label, q };
  });
}

const CADENCE_COLORS: Record<string, string> = {
  authentic: "var(--accent)",
  plagal: "#6ee7b7",
  half: "#fbbf24",
  deceptive: "#f87171",
};

export default function Analysis({ analysis, notes, audioName, numNotes }: Props) {
  if (!analysis?.key) {
    return (
      <p className="muted">
        Analysis data will appear once the backend processing is complete.
      </p>
    );
  }

  const chords = getDiatonicChords(analysis.key.tonic, analysis.key.mode);
  const noteStats = computeNoteStats(notes);

  const chordLabels = chords.map((c) => c.label).join(", ");
  const theoryText =
    analysis.key.mode === "major"
      ? `This piece is in ${analysis.key.tonic} major. Common chords: ${chordLabels}.`
      : `This piece is in ${analysis.key.tonic} minor. Common chords: ${chordLabels}.`;

  const cKey = Math.round(analysis.key.confidence * 100);
  const cTempo = analysis.tempo ? Math.round(analysis.tempo.confidence * 100) : null;
  const cSig = analysis.time_signature ? Math.round(analysis.time_signature.confidence * 100) : null;

  const progression = (analysis.chords ?? [])
    .filter((c) => c.quality)
    .map((c) => {
      const q = c.quality;
      const label = q === "M" ? c.root : q === "m" ? `${c.root}m` : `${c.root}${q}`;
      return { label, start: c.start, end: c.end };
    });

  const romanNumerals = analysis.roman_numerals ?? [];
  const cadences = analysis.cadences ?? [];
  const modulations = analysis.modulations ?? [];
  const voiceLeading = analysis.voice_leading;

  return (
    <div>
      <div className="section-label">Track: {audioName}</div>

      <div className="stat-grid">
        <div className="stat fade-in">
          <span className="s-label">Key</span>
          <span className="s-value">{analysis.key.tonic} {analysis.key.mode}</span>
          <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cKey}%` }} /></div>
          <span className="confidence-pct">{cKey}%</span>
        </div>
        <div className="stat fade-in" style={{ animationDelay: ".05s" }}>
          <span className="s-label">Tempo</span>
          <span className="s-value">{analysis.tempo ? `${analysis.tempo.bpm} BPM` : "—"}</span>
          {cTempo !== null && (
            <>
              <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cTempo}%` }} /></div>
              <span className="confidence-pct">{cTempo}%</span>
            </>
          )}
        </div>
        <div className="stat fade-in" style={{ animationDelay: ".1s" }}>
          <span className="s-label">Time signature</span>
          <span className="s-value">{analysis.time_signature ? `${analysis.time_signature.numerator}/${analysis.time_signature.denominator}` : "—"}</span>
          {cSig !== null && (
            <>
              <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cSig}%` }} /></div>
              <span className="confidence-pct">{cSig}%</span>
            </>
          )}
        </div>
      </div>

      {romanNumerals.length > 0 && (
        <>
          <div className="section-label">Roman numeral analysis</div>
          <div className="chips" style={{ flexWrap: "wrap" }}>
            {romanNumerals.map((rn, i) => {
              const cadMatch = cadences.find((c) => Math.abs(c.position - rn.start) < 0.5);
              return (
                <span
                  key={i}
                  className="chip"
                  style={cadMatch ? {
                    borderColor: CADENCE_COLORS[cadMatch.type] ?? "var(--border-strong)",
                    boxShadow: `0 0 6px ${CADENCE_COLORS[cadMatch.type] ?? "var(--border-strong)"}`,
                  } : undefined}
                  title={cadMatch ? `Cadence: ${cadMatch.type} (${cadMatch.chords.join(" → ")})` : undefined}
                >
                  {rn.figure}
                  {cadMatch && (
                    <span style={{
                      marginLeft: 4,
                      fontSize: "var(--fs-xs)",
                      color: CADENCE_COLORS[cadMatch.type],
                      fontWeight: 600,
                    }}>
                      {cadMatch.type[0].toUpperCase()}
                    </span>
                  )}
                </span>
              );
            })}
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
            {romanNumerals.length} chords analyzed · cadences highlighted with colored borders
          </p>
        </>
      )}

      {cadences.length > 0 && (
        <>
          <div className="section-label">Cadences</div>
          <div className="chips">
            {cadences.map((c, i) => (
              <span
                key={i}
                className="chip"
                style={{
                  borderColor: CADENCE_COLORS[c.type] ?? "var(--border)",
                  color: CADENCE_COLORS[c.type] ?? "var(--text)",
                }}
              >
                {c.type} ({c.chords.join(" → ")})
              </span>
            ))}
          </div>
        </>
      )}

      {modulations.length > 0 && (
        <>
          <div className="section-label">Modulations</div>
          <div className="chips">
            {modulations.map((m, i) => (
              <span key={i} className="chip">
                {m.from_key} → {m.to_key}
                <span className="muted" style={{ marginLeft: 4, fontSize: "var(--fs-xs)" }}>
                  @ {m.position.toFixed(1)}s
                </span>
              </span>
            ))}
          </div>
        </>
      )}

      {voiceLeading && (
        <>
          <div className="section-label">Voice leading</div>
          <div className="stat-grid">
            {(["contrary", "parallel", "oblique", "similar"] as const).map((motion) => (
              <div key={motion} className="stat">
                <span className="s-label">{motion}</span>
                <span className="s-value">{Math.round(voiceLeading[motion] * 100)}%</span>
              </div>
            ))}
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
            {voiceLeading.motion_summary}
          </p>
        </>
      )}

      <div className="section-label">Diatonic chords</div>
      <div className="chips">
        {chords.map((c, i) => (
          <span key={i} className={`chip-q ${c.q}`}>{c.label}</span>
        ))}
      </div>

      {progression.length > 0 && (
        <>
          <div className="section-label">Chord progression</div>
          <div className="chips">
            {progression.map((c, i) => (
              <span key={i} className="chip">{c.label}</span>
            ))}
          </div>
            <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
              {progression.length} segments · {progression[0].start.toFixed(1)}s–{progression[progression.length - 1].end.toFixed(1)}s
            </p>
        </>
      )}

      <div className="section-label">Note statistics</div>
      <div className="stat-grid">
        <div className="stat">
          <span className="s-label">Pitch range</span>
          <span className="s-value">
            {SHARP_NOTE_NAMES[noteStats.pitchRange.low % 12]}–{SHARP_NOTE_NAMES[noteStats.pitchRange.high % 12]}
          </span>
          <span className="confidence-pct">{noteStats.pitchRange.span} semitones</span>
        </div>
        <div className="stat">
          <span className="s-label">Note count</span>
          <span className="s-value">{notes.length}</span>
        </div>
        <div className="stat">
          <span className="s-label">Density</span>
          <span className="s-value">{noteStats.density}/s</span>
        </div>
      </div>

      <div className="card" style={{ marginTop: "var(--s-4)", borderColor: "var(--border-strong)", color: "var(--muted)", fontSize: "var(--fs-sm)", lineHeight: "var(--line-height-base)" }}>
        {theoryText}
      </div>
    </div>
  );
}
