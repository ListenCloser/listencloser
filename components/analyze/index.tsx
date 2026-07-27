/**
 * Analysis display — redesigned for UX-016/017/018.
 *
 * UX-016: Answer key questions in plain language
 * UX-017: Visual analysis (chord timeline, modulation markers)
 * UX-018: Human-readable explanations instead of raw statistics
 *
 * Design principle: Lead with insights, follow with data.
 * The user should understand their piece in 5 seconds.
 */

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

const CADENCE_COLORS: Record<string, string> = {
  authentic: "var(--accent)",
  plagal: "#6ee7b7",
  half: "#fbbf24",
  deceptive: "#f87171",
};

const CADENCE_DESCRIPTIONS: Record<string, string> = {
  authentic: "A strong resolution (V→I) that feels conclusive.",
  plagal: "A gentle 'Amen' cadence (IV→I).",
  half: "An open-ended pause that creates expectation.",
  deceptive: "An unexpected turn that surprises the listener.",
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

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function generateInsights(analysis: NonNullable<TranscribeResult["analysis"]>, notes: TranscribeResult["notes"]): string[] {
  const insights: string[] = [];

  // Key insight
  const keyName = `${analysis.key.tonic} ${analysis.key.mode}`;
  const conf = Math.round(analysis.key.confidence * 100);
  if (conf >= 80) {
    insights.push(`Likely in ${keyName}.`);
  } else if (conf >= 50) {
    insights.push(`Probably in ${keyName}, though the key is somewhat ambiguous.`);
  } else {
    insights.push(`The key is uncertain — may be ${keyName} or a related mode.`);
  }

  // Tempo insight
  if (analysis.tempo) {
    const bpm = Math.round(analysis.tempo.bpm);
    if (bpm < 80) insights.push(`Slow tempo at ${bpm} BPM — suggests a ballad or adagio feel.`);
    else if (bpm < 120) insights.push(`Moderate tempo at ${bpm} BPM.`);
    else if (bpm < 160) insights.push(`Upbeat tempo at ${bpm} BPM.`);
    else insights.push(`Fast tempo at ${bpm} BPM — suggests energy and drive.`);
  }

  // Modulation insight
  if (analysis.modulations && analysis.modulations.length > 0) {
    const mods = analysis.modulations;
    insights.push(`${mods.length} key change${mods.length > 1 ? "s" : ""} detected — the harmony shifts at ${mods.map(m => formatTime(m.position)).join(", ")}.`);
  }

  // Cadence insight
  if (analysis.cadences && analysis.cadences.length > 0) {
    const types = analysis.cadences.map(c => c.type);
    const dominant = types.sort((a, b) => types.filter(v => v === b).length - types.filter(v => v === a).length)[0];
    if (dominant) {
      insights.push(`The piece relies heavily on ${dominant} cadences — ${CADENCE_DESCRIPTIONS[dominant] || ""}`);
    }
  }

  // Note density insight
  const noteStats = computeNoteStats(notes);

  // Rhythm insight (ISSUE-010)
  if (analysis.rhythm) {
    const r = analysis.rhythm;
    if (r.syncopation_ratio > 0.3) {
      insights.push(`High syncopation (${Math.round(r.syncopation_ratio * 100)}%) — rhythmic and groove-oriented.`);
    } else if (r.syncopation_ratio < 0.1) {
      insights.push(`Straight rhythm (${Math.round(r.syncopation_ratio * 100)}% syncopation) — on-the-beat feel.`);
    }
    if (r.rhythmic_density > 8) {
      insights.push(`Dense rhythm (${r.rhythmic_density} notes/sec) — busy, virtuosic writing.`);
    }
  }
  if (noteStats.density > 8) {
    insights.push(`High note density (${noteStats.density}/s) — dense, virtuosic writing.`);
  } else if (noteStats.density < 2) {
    insights.push(`Low note density (${noteStats.density}/s) — sparse, lyrical writing.`);
  }

  return insights;
}

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
  const insights = generateInsights(analysis, notes);

  const cKey = Math.round(analysis.key.confidence * 100);
  const cTempo = analysis.tempo ? Math.round(analysis.tempo.confidence * 100) : null;
  const cSig = analysis.time_signature ? Math.round(analysis.time_signature.confidence * 100) : null;

  const progression = (analysis.chords ?? [])
    .filter((c) => c.quality)
    .map((c) => {
      const q = c.quality;
      const label = q === "M" ? c.root : q === "m" ? `${c.root}m` : `${c.root}${q}`;
      return { label, start: c.start, end: c.end, quality: c.quality };
    });

  const romanNumerals = analysis.roman_numerals ?? [];
  const cadences = analysis.cadences ?? [];
  const modulations = analysis.modulations ?? [];
  const voiceLeading = analysis.voice_leading;

  const totalDuration = notes.length > 0 ? Math.max(...notes.map(n => n.end)) : 0;

  return (
    <div>
      {/* ── Summary insights (UX-018: human-readable) ── */}
      <div className="section-label">Summary</div>
      <div className="stat" style={{ marginBottom: "var(--s-3)" }}>
        {insights.map((insight, i) => (
          <p key={i} style={{ margin: "var(--s-1) 0", fontSize: "var(--fs-sm)", lineHeight: "var(--line-height-base)" }}>
            {insight}
          </p>
        ))}
      </div>

      {/* ── Key metrics ── */}
      <div className="stat-grid">
        <div className="stat fade-in">
          <span className="s-label">Key</span>
          <span className="s-value">{analysis.key.tonic} {analysis.key.mode}</span>
          <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cKey}%` }} /></div>
          <span className="confidence-pct">{cKey}% confidence</span>
        </div>
        <div className="stat fade-in" style={{ animationDelay: ".05s" }}>
          <span className="s-label">Tempo</span>
          <span className="s-value">{analysis.tempo ? `${Math.round(analysis.tempo.bpm)} BPM` : "—"}</span>
          {cTempo !== null && (
            <>
              <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cTempo}%` }} /></div>
              <span className="confidence-pct">{cTempo}% confidence</span>
            </>
          )}
        </div>
        <div className="stat fade-in" style={{ animationDelay: ".1s" }}>
          <span className="s-label">Time</span>
          <span className="s-value">{analysis.time_signature ? `${analysis.time_signature.numerator}/${analysis.time_signature.denominator}` : "—"}</span>
          {cSig !== null && (
            <>
              <div className="confidence-track"><div className="confidence-fill" style={{ width: `${cSig}%` }} /></div>
              <span className="confidence-pct">{cSig}% confidence</span>
            </>
          )}
        </div>
      </div>

      {/* ── Chord timeline (UX-017: visual analysis) ── */}
      {progression.length > 0 && totalDuration > 0 && (
        <>
          <div className="section-label">Chord Timeline</div>
          <div style={{ position: "relative", height: 40, background: "var(--panel-3)", borderRadius: "var(--r-sm)", overflow: "hidden", marginBottom: "var(--s-2)" }}>
            {progression.map((c, i) => {
              const left = (c.start / totalDuration) * 100;
              const width = ((c.end - c.start) / totalDuration) * 100;
              const isMinor = c.quality === "m";
              return (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: `${left}%`,
                    width: `${Math.max(width, 0.5)}%`,
                    height: "100%",
                    background: isMinor ? "var(--accent-soft-2)" : "var(--accent-soft)",
                    borderRight: "1px solid var(--panel)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "var(--fs-xs)",
                    fontWeight: 500,
                    color: isMinor ? "var(--accent-2)" : "var(--accent)",
                    overflow: "hidden",
                    whiteSpace: "nowrap",
                  }}
                  title={`${c.label} (${formatTime(c.start)}–${formatTime(c.end)})`}
                >
                  {width > 3 && c.label}
                </div>
              );
            })}
            {/* Modulation markers */}
            {modulations.map((m, i) => (
              <div
                key={`mod-${i}`}
                style={{
                  position: "absolute",
                  left: `${(m.position / totalDuration) * 100}%`,
                  top: 0,
                  width: 2,
                  height: "100%",
                  background: "var(--danger)",
                  opacity: 0.7,
                }}
                title={`Modulation: ${m.from_key} → ${m.to_key}`}
              />
            ))}
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "0 0 var(--s-3)" }}>
            {progression.length} chord segments · {formatTime(totalDuration)} duration
            {modulations.length > 0 && ` · ${modulations.length} key change${modulations.length > 1 ? "s" : ""}`}
          </p>
        </>
      )}

      {/* ── Roman numeral analysis ── */}
      {romanNumerals.length > 0 && (
        <>
          <div className="section-label">Roman Numeral Analysis</div>
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
            {romanNumerals.length} chords · cadences highlighted with colored borders
          </p>
        </>
      )}

      {/* ── Cadences ── */}
      {cadences.length > 0 && (
        <>
          <div className="section-label">Cadences</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
            {cadences.map((c, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: CADENCE_COLORS[c.type] ?? "var(--muted)",
                  }}
                />
                <span style={{ fontSize: "var(--fs-sm)", fontWeight: 500, color: CADENCE_COLORS[c.type] ?? "var(--text)" }}>
                  {c.type}
                </span>
                <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                  {c.chords.join(" → ")} at {formatTime(c.position)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Modulations ── */}
      {modulations.length > 0 && (
        <>
          <div className="section-label">Key Changes</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
            {modulations.map((m, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
                <span style={{ fontSize: "var(--fs-sm)" }}>
                  {m.from_key} → {m.to_key}
                </span>
                <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                  at {formatTime(m.position)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Voice leading ── */}
      {voiceLeading && (
        <>
          <div className="section-label">Voice Leading</div>
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

      {/* ── Diatonic chords ── */}
      <div className="section-label">Diatonic Chords in {analysis.key.tonic} {analysis.key.mode}</div>
      <div className="chips">
        {chords.map((c, i) => (
          <span key={i} className={`chip-q ${c.q}`}>{c.label}</span>
        ))}
      </div>

      {/* ── Note statistics ── */}
      <div className="section-label">Note Statistics</div>
      <div className="stat-grid">
        <div className="stat">
          <span className="s-label">Pitch Range</span>
          <span className="s-value">
            {SHARP_NOTE_NAMES[noteStats.pitchRange.low % 12]}–{SHARP_NOTE_NAMES[noteStats.pitchRange.high % 12]}
          </span>
          <span className="confidence-pct">{noteStats.pitchRange.span} semitones</span>
        </div>
        <div className="stat">
          <span className="s-label">Note Count</span>
          <span className="s-value">{notes.length}</span>
        </div>
        <div className="stat">
          <span className="s-label">Density</span>
          <span className="s-value">{noteStats.density}/s</span>
        </div>
      </div>

      {/* ── Rhythm (ISSUE-010) ── */}
      {analysis.rhythm && (
        <>
          <div className="section-label">Rhythm</div>
          <div className="stat-grid">
            <div className="stat">
              <span className="s-label">Beats</span>
              <span className="s-value">{analysis.rhythm.beat_count}</span>
            </div>
            <div className="stat">
              <span className="s-label">Syncopation</span>
              <span className="s-value">{Math.round(analysis.rhythm.syncopation_ratio * 100)}%</span>
            </div>
            <div className="stat">
              <span className="s-label">Note Duration</span>
              <span className="s-value">{analysis.rhythm.avg_note_duration.toFixed(2)}s</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
