"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";

const TABS = [
  { id: "insights", label: "Insights" },
  { id: "commands", label: "Commands" },
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
        <div style={{ display: "flex", gap: "var(--s-1)" }}>
          {TABS.map((t) => (
            <button
              key={t.id}
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
        {activeTab === "commands" && <CommandTab />}
      </div>
    </div>
  );
}

function InsightsTab() {
  const { workspace } = useWorkspace();
  const summary = workspace.insights.filter((item) =>
    ["key", "tempo", "time_signature"].includes(item.kind),
  );
  const details = workspace.insights.filter((item) =>
    !["key", "tempo", "time_signature"].includes(item.kind),
  );

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
      <div className="stat-grid">
        {summary.map((item) => (
          <div className="stat" key={item.id}>
            <span className="s-label">{item.kind.replaceAll("_", " ")}</span>
            <span className="s-value">{item.claim.replace(/^[^:]+:\s*/, "")}</span>
            <span className="s-label">{Math.round(item.confidence * 100)}% confidence</span>
          </div>
        ))}
      </div>
      {details.slice(0, 30).map((item) => (
        <div className="stat" key={item.id}>
          <span className="s-label">{item.kind.replaceAll("_", " ")}</span>
          <span className="s-value" style={{ fontSize: "var(--fs-xs)" }}>{item.claim}</span>
        </div>
      ))}
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
      <div className="section-label" style={{ margin: 0 }}>Work commands</div>
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
