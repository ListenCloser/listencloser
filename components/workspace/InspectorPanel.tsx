"use client";

import { useMemo, useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

const TABS = [
  { id: "insights", label: "Insights" },
  { id: "studio", label: "Studio" },
  { id: "commands", label: "Shortcuts" },
] as const;

type TabId = (typeof TABS)[number]["id"];

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
        {activeTab === "commands" && <CommandTab />}
      </div>
    </div>
  );
}

function StudioTab() {
  const { workspace, requestComparison, requestVariation } = useWorkspace();
  const { transport, play, setActiveSource } = useTransport();
  const [semitones, setSemitones] = useState(0);
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const takes = workspace.takes;
  const sourceTake = takes[0];
  const operation = workspace.studioOperation;
  const variationLabel = useMemo(
    () => semitones === 0 ? "Duplicate take" : `Transpose ${semitones > 0 ? "+" : ""}${semitones} semitones`,
    [semitones],
  );

  if (!sourceTake) {
    return <p className="insight-intro">Create a transcription first. The Studio works from persisted MIDI takes, never from a temporary browser file.</p>;
  }

  return (
    <div style={{ display: "grid", gap: "var(--s-4)" }}>
      <div>
        <div className="section-label" style={{ margin: 0 }}>Composition studio</div>
        <p className="insight-intro">Every operation creates an immutable take with its own playback, score, and analysis. This first tool is intentionally transparent: it changes pitch, not rhythm or melody.</p>
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
        <h3 id="takes-title">Saved takes</h3>
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
  const { workspace, expandRepresentation, focusRepresentation } = useWorkspace();
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  const summary = workspace.insights.filter((item) =>
    ["key", "tempo", "time_signature"].includes(item.kind),
  );
  const details = workspace.insights.filter((item) =>
    !["key", "tempo", "time_signature"].includes(item.kind),
  );
  const groups = [
    { label: "Harmony", kinds: ["chord", "roman_numeral", "cadence", "modulation"] },
    { label: "Melody & rhythm", kinds: ["melody", "rhythm", "range", "density", "syncopation"] },
    { label: "Sound", kinds: ["loudness", "spectral_centroid", "audio_descriptor"] },
  ];

  function seekToEvidence(item: (typeof workspace.insights)[number]) {
    const seconds = item.span.start_seconds;
    if (typeof seconds === "number") seek(seconds);
    else if (typeof item.span.start_beat === "number" && timeline.bpm > 0) {
      seek(item.span.start_beat * 60 / timeline.bpm);
    }
    expandRepresentation("piano_roll");
    focusRepresentation("piano_roll");
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div className="section-label" style={{ margin: 0 }}>Analysis</div>
      <p className="insight-intro">Computed from the saved transcription. Treat lower-confidence claims as suggestions to verify by ear.</p>
      <div className="stat-grid">
        {summary.map((item) => (
          <div className="stat" key={item.id}>
            <span className="s-label">{item.kind.replaceAll("_", " ")}</span>
            <span className="s-value">{item.claim.replace(/^[^:]+:\s*/, "")}</span>
            <span className="s-label">{Math.round(item.confidence * 100)}% confidence</span>
          </div>
        ))}
      </div>
      {groups.map((group) => {
        const items = details.filter((item) => group.kinds.some((kind) => item.kind.includes(kind)));
        if (!items.length) return null;
        return (
          <section className="insight-group" key={group.label}>
            <h3>{group.label}</h3>
            {items.slice(0, 20).map((item) => {
              const position = spanLabel(item);
              return (
                <button type="button" className="insight-row" key={item.id} onClick={() => seekToEvidence(item)}>
                  <span className="insight-claim">{item.claim}</span>
                  <span className="insight-meta">
                    {position && <span>{position}</span>}
                    <span>{Math.round(item.confidence * 100)}%</span>
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
          {details.slice(0, 20).map((item) => (
            <button type="button" className="insight-row" key={item.id} onClick={() => seekToEvidence(item)}>
              <span className="insight-claim">{item.claim}</span>
              <span className="insight-meta"><span>{Math.round(item.confidence * 100)}%</span></span>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}

type CommandMessage = { role: "user" | "system"; text: string };

function CommandTab() {
  const {
    workspace,
    expandRepresentation,
    focusRepresentation,
    requestImport,
  } = useWorkspace();
  const { transport, play, setActiveSource } = useTransport();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<CommandMessage[]>([
    {
      role: "system",
      text: "Commands operate on the active persisted work. Type help to see what is available.",
    },
  ]);

  function runCommand(raw: string) {
    const command = raw.trim().toLowerCase();
    if (!command) return;
    let response = "Unknown command. Type help for the supported operations.";

    if (command === "help") {
      response = "Available: summarize, play original, play transcription, show score, show piano roll, import.";
    } else if (command === "summarize" || command === "summary") {
      response = workspace.insights.length
        ? workspace.insights
            .filter((item) => ["key", "tempo", "time_signature"].includes(item.kind))
            .map((item) => item.claim)
            .join(" · ") || `${workspace.insights.length} detailed insights are available.`
        : "No persisted analysis is available for the active work.";
    } else if (command === "import" || command === "import audio") {
      requestImport();
      response = "Opening the audio importer.";
    } else if (command === "show score" || command === "score") {
      const exists = workspace.representations.some((item) => item.kind === "score");
      if (exists) {
        expandRepresentation("score");
        focusRepresentation("score");
        response = "Focused the persisted MusicXML score.";
      } else response = "This work does not have a score artifact yet.";
    } else if (command === "show piano roll" || command === "piano roll") {
      const exists = workspace.representations.some((item) => item.kind === "piano_roll");
      if (exists) {
        expandRepresentation("piano_roll");
        focusRepresentation("piano_roll");
        response = "Focused the note-level transcription.";
      } else response = "This work does not have a MIDI transcription yet.";
    } else if (command === "play original" || command === "play transcription") {
      const target = command.endsWith("original") ? "Original audio" : "Transcription playback";
      const source = transport.sources.find((item) => item.label === target);
      if (source) {
        setActiveSource(source);
        window.setTimeout(play, 0);
        response = `Playing ${target.toLowerCase()}.`;
      } else response = `${target} is not available for this work.`;
    } else if (["compare", "correct", "generate", "continue"].some((word) => command.includes(word))) {
      response = "That capability is not production-ready yet. It is intentionally not exposed as a working action.";
    }

    setMessages((current) => [
      ...current,
      { role: "user", text: raw.trim() },
      { role: "system", text: response },
    ]);
    setInput("");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)", minHeight: "100%" }}>
      <div className="section-label" style={{ margin: 0 }}>Work shortcuts</div>
      <p className="insight-intro">Deterministic controls for the active work—not an AI chat.</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)", flex: 1 }}>
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            style={{
              alignSelf: message.role === "user" ? "flex-end" : "stretch",
              padding: "var(--s-2) var(--s-3)",
              borderRadius: "var(--r-md)",
              background: message.role === "user" ? "var(--accent-soft)" : "var(--panel-2)",
              color: message.role === "user" ? "var(--accent)" : "var(--muted)",
              fontSize: "var(--fs-xs)",
              lineHeight: 1.5,
            }}
          >
            {message.text}
          </div>
        ))}
      </div>
      <form onSubmit={(event) => { event.preventDefault(); runCommand(input); }} style={{ display: "flex", gap: "var(--s-2)" }}>
        <input
          className="input"
          aria-label="Work command"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="summarize"
        />
        <button className="btn btn-primary" type="submit">Run</button>
      </form>
    </div>
  );
}
