"use client";

import { useMemo, useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

const TABS = [
  { id: "insights", label: "Analysis" },
  { id: "studio", label: "Versions" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function formatConfidence(confidence: number | null): string {
  return confidence == null ? "—" : `${Math.round(confidence * 100)}%`;
}

const NOT_DETECTED = "Not confidently detected";

function methodLabel(provenance: Record<string, unknown>): string | null {
  const method = provenance.method;
  if (method === "detected" || method === "inferred" || method === "heuristic") return method;
  return null;
}

export default function InspectorPanel() {
  const { workspace, toggleInspector } = useWorkspace();
  const [activeTab, setActiveTab] = useState<TabId>("insights");

  if (workspace.inspectorCollapsed) {
    return (
      <button
        className="icon-btn ghost"
        onClick={toggleInspector}
        style={{
          writingMode: "vertical-rl",
          textOrientation: "mixed",
          padding: "var(--s-3) var(--s-2)",
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
          borderLeft: "1px solid var(--border)",
          flexShrink: 0,
        }}
        title="Open inspector"
      >
        Inspector ▸
      </button>
    );
  }

  return (
    <div className="studio-inspector"
      style={{
        display: "flex",
        flexDirection: "column",
        width: 280,
        flexShrink: 0,
        borderLeft: "1px solid var(--border)",
        background: "var(--panel)",
        overflow: "hidden",
        fontSize: "var(--fs-sm)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--s-2) var(--s-3)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div role="tablist" aria-label="Inspector views" style={{ display: "flex", gap: "var(--s-1)" }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={activeTab === t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                padding: "4px 10px",
                borderRadius: "var(--r-full)",
                border: "none",
                background:
                  activeTab === t.id ? "var(--accent)" : "transparent",
                color: activeTab === t.id ? "var(--bg)" : "var(--muted)",
                fontSize: "var(--fs-xs)",
                fontWeight: "var(--fw-medium)",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "all var(--dur) var(--ease)",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <button
          className="icon-btn ghost"
          onClick={toggleInspector}
          style={{ padding: "2px 6px", fontSize: 10 }}
          title="Close inspector"
        >
          ✕
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-3)" }}>
        {activeTab === "insights" && <InsightsTab />}
        {activeTab === "studio" && <StudioTab />}
      </div>
    </div>
  );
}

function StudioTab() {
  const { workspace, requestComparison, requestVariation } = useWorkspace();
  const { transport, play, setActiveSource } = useTransport();
  const [semitones, setSemitones] = useState(2);
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const takes = workspace.takes;
  const sourceTake = takes.find((take) => take.label === "Transcription") ?? takes[0];
  const operation = workspace.studioOperation;
  const variationLabel = useMemo(
    () => semitones === 0 ? "Duplicate take" : `Transpose ${semitones > 0 ? "+" : ""}${semitones} semitones`,
    [semitones],
  );

  if (!sourceTake) {
    return <p className="insight-intro">Create a transcription first. Versions work from saved MIDI takes, never from a temporary browser file.</p>;
  }

  return (
    <div style={{ display: "grid", gap: "var(--s-4)" }}>
      <div>
        <div className="section-label" style={{ margin: 0 }}>Versions & variations</div>
        <p className="insight-intro">Every operation creates a saved take with its own playback, score, and analysis. This first variation is intentionally transparent: it changes pitch, not rhythm or melody.</p>
      </div>
      <section className="insight-group" aria-labelledby="variation-title">
        <h3 id="variation-title">Make a variation</h3>
        <label htmlFor="transpose-semitones" style={{ display: "grid", gap: 6, color: "var(--muted)", fontSize: "var(--fs-xs)" }}>
          <span>{variationLabel}</span>
          <input id="transpose-semitones" type="range" min={-12} max={12} step={1} value={semitones} onChange={(event) => setSemitones(Number(event.target.value))} />
        </label>
        <button type="button" className="btn btn-primary" style={{ marginTop: "var(--s-3)", width: "100%" }} disabled={operation.state === "running"} onClick={() => requestVariation(sourceTake.versionId, semitones)}>
          Create playable take
        </button>
      </section>
      <section className="insight-group" aria-labelledby="compare-title">
        <h3 id="compare-title">Compare takes</h3>
        <p className="insight-intro">Compare saved note events. The result records additions, removals, and duration changes with provenance.</p>
        <div style={{ display: "grid", gap: "var(--s-2)" }}>
          <select className="input" aria-label="First take" value={compareA} onChange={(event) => setCompareA(event.target.value)}>
            <option value="">Choose first take</option>
            {takes.map((take) => <option key={take.versionId} value={take.versionId}>{take.label}</option>)}
          </select>
          <select className="input" aria-label="Second take" value={compareB} onChange={(event) => setCompareB(event.target.value)}>
            <option value="">Choose second take</option>
            {takes.map((take) => <option key={take.versionId} value={take.versionId}>{take.label}</option>)}
          </select>
          <button type="button" className="btn" disabled={!compareA || !compareB || compareA === compareB || operation.state === "running"} onClick={() => requestComparison(compareA, compareB)}>
            Compare selected takes
          </button>
        </div>
      </section>
      <section className="insight-group" aria-labelledby="takes-title">
        <h3 id="takes-title">Saved versions</h3>
        <div style={{ display: "grid", gap: "var(--s-2)" }}>
          {takes.map((take) => {
            const source = transport.sources.find((item) => item.label === `${take.label} playback`);
            return (
              <div key={take.versionId} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--s-2)" }}>
                <span style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>{take.label}</span>
                {source && <button type="button" className="btn" style={{ padding: "3px 8px", fontSize: "var(--fs-xs)" }} onClick={() => { setActiveSource(source); window.setTimeout(play, 0); }}>Audition</button>}
              </div>
            );
          })}
        </div>
      </section>
      {operation.state !== "idle" && (
        <div className={`operation-card${operation.state === "error" ? " operation-card-warning" : ""}`} role="status" aria-live="polite">
          <strong>{operation.label}</strong>
          {operation.message && <span>{operation.message}</span>}
        </div>
      )}
    </div>
  );
}

function InsightsTab() {
  const { workspace, setActiveRepresentation } = useWorkspace();
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  const summary = workspace.insights.filter((item) =>
    ["key", "tempo", "time_signature"].includes(item.kind),
  );
  const details = workspace.insights.filter((item) =>
    !["key", "tempo", "time_signature"].includes(item.kind),
  );
  const groups = [
    { label: "Form & pulse", kinds: ["audio_structure", "audio_tempo", "section"] },
    { label: "Harmony", kinds: ["chord", "roman_numeral", "cadence", "cadence_candidate", "modulation"] },
    { label: "Melody & rhythm", kinds: ["melody", "rhythm", "range", "density", "syncopation"] },
    { label: "Sound", kinds: ["loudness", "spectral_centroid", "audio_descriptor"] },
  ];

  function seekToEvidence(item: (typeof workspace.insights)[number]) {
    const seconds = item.span.start_seconds;
    if (typeof seconds === "number") seek(seconds);
    else if (typeof item.span.start_beat === "number" && timeline.bpm > 0) {
      seek(item.span.start_beat * 60 / timeline.bpm);
    }
    setActiveRepresentation("piano_roll");
  }

  function spanLabel(item: (typeof workspace.insights)[number]): string | null {
    if (typeof item.span.start_measure === "number") return `Measure ${Math.floor(item.span.start_measure) + 1}`;
    if (typeof item.span.start_beat === "number") return `Beat ${item.span.start_beat.toFixed(1)}`;
    if (typeof item.span.start_seconds === "number") {
      const minutes = Math.floor(item.span.start_seconds / 60);
      const seconds = Math.floor(item.span.start_seconds % 60).toString().padStart(2, "0");
      return `${minutes}:${seconds}`;
    }
    return null;
  }

  if (workspace.insights.length === 0) {
    return (
      <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", padding: "var(--s-4) 0", textAlign: "center" }}>
        Analysis results will appear here after transcription.
      </div>
    );
  }

  const key = summary.find((item) => item.kind === "key")?.claim.replace(/^Key:\s*/, "") ?? "Key not confidently detected";
  const tempo = summary.find((item) => item.kind === "tempo")?.evidence.bpm;
  const meter = summary.find((item) => item.kind === "time_signature")?.claim.replace(/^Time Signature:\s*/, "") ?? null;
  const chordPath = details.filter((item) => item.kind === "chord").slice(0, 8);
  const primaryStats = [
    { label: "key", item: summary.find((item) => item.kind === "key") },
    { label: "tempo", item: summary.find((item) => item.kind === "tempo") },
    { label: "time signature", item: summary.find((item) => item.kind === "time_signature") },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div className="section-label" style={{ margin: 0 }}>What this piece is doing</div>
      <p className="insight-intro">{[key, typeof tempo === "number" ? `${Math.round(tempo)} BPM` : null, meter].filter(Boolean).join(" · ") || "Analysis is available below."} These are listening hypotheses from the saved transcription, not facts about the original recording.</p>
      <div className="stat-grid">
        {primaryStats.map(({ label, item }) => (
          <div className="stat" key={label}>
            <span className="s-label">{label}</span>
            <span className="s-value">{item ? item.claim.replace(/^[^:]+:\s*/, "") : NOT_DETECTED}</span>
            <span className="s-label">{item ? `${formatConfidence(item.confidence)} confidence` : "unavailable"}</span>
          </div>
        ))}
      </div>
      {chordPath.length > 0 && (
        <section className="insight-group">
          <h3>Harmonic path</h3>
          <div className="rn-chips">
            {chordPath.map((item) => <button type="button" className="rn-chip" key={item.id} onClick={() => seekToEvidence(item)}>{item.claim}</button>)}
          </div>
          <p className="insight-intro">Select a chord to hear and inspect its location.</p>
        </section>
      )}
      {groups.map((group) => {
        const items = details.filter((item) => group.kinds.some((kind) => item.kind.includes(kind)));
        const visibleItems = items.filter((item) => item.kind !== "chord").slice(0, 8);
        if (!visibleItems.length) return null;
        return (
          <section className="insight-group" key={group.label}>
            <h3>{group.label}</h3>
            {visibleItems.map((item) => {
              const position = spanLabel(item);
              return (
                <button type="button" className="insight-row" key={item.id} onClick={() => seekToEvidence(item)}>
                  <span className="insight-claim">{item.claim}</span>
                  <span className="insight-meta">
                    {position && <span>{position}</span>}
                    {methodLabel(item.provenance) && <span>{methodLabel(item.provenance)}</span>}
                    <span>{formatConfidence(item.confidence)}</span>
                  </span>
                </button>
              );
            })}
          </section>
        );
      })}
      {details.length > 0 && groups.every((group) => !details.some((item) => group.kinds.some((kind) => item.kind.includes(kind)))) && (
        <section className="insight-group">
          <h3>Details</h3>
          {details.slice(0, 8).map((item) => (
            <button type="button" className="insight-row" key={item.id} onClick={() => seekToEvidence(item)}>
              <span className="insight-claim">{item.claim}</span>
              <span className="insight-meta"><span>{formatConfidence(item.confidence)}</span></span>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}
