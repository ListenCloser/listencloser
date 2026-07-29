"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useSelection } from "@/lib/stores/selection";
import MusicChat from "@/components/MusicChat";

const TABS = [
  { id: "selection", label: "Selection" },
  { id: "properties", label: "Properties" },
  { id: "insights", label: "Insights" },
  { id: "ai", label: "AI" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function InspectorPanel() {
  const { workspace, toggleInspector } = useWorkspace();
  const [activeTab, setActiveTab] = useState<TabId>("selection");

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
    <div
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
        {activeTab === "selection" && <SelectionTab />}
        {activeTab === "properties" && <PropertiesTab />}
        {activeTab === "insights" && <InsightsTab />}
        {activeTab === "ai" && <AITab />}
      </div>
    </div>
  );
}

function SelectionTab() {
  const { selection, clearSelection, hasSelection } = useSelection();

  if (!hasSelection()) {
    return (
      <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", padding: "var(--s-4) 0", textAlign: "center" }}>
        No selection active.
        <br />
        Click and drag in a representation to select.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div className="section-label" style={{ margin: 0 }}>Active Selection</div>

      {selection.timeStart !== null && (
        <div className="stat">
          <div className="s-label">Time</div>
          <div className="s-value" style={{ fontSize: "var(--fs-sm)" }}>
            {selection.timeStart.toFixed(2)}s – {selection.timeEnd?.toFixed(2) ?? "—"}s
          </div>
        </div>
      )}

      {selection.beatStart !== null && (
        <div className="stat">
          <div className="s-label">Beats</div>
          <div className="s-value" style={{ fontSize: "var(--fs-sm)" }}>
            {selection.beatStart} – {selection.beatEnd ?? "—"}
          </div>
        </div>
      )}

      {selection.measureStart !== null && (
        <div className="stat">
          <div className="s-label">Measures</div>
          <div className="s-value" style={{ fontSize: "var(--fs-sm)" }}>
            {selection.measureStart} – {selection.measureEnd ?? "—"}
          </div>
        </div>
      )}

      {selection.noteIndices.length > 0 && (
        <div className="stat">
          <div className="s-label">Notes</div>
          <div className="s-value" style={{ fontSize: "var(--fs-sm)" }}>
            {selection.noteIndices.length} selected
          </div>
        </div>
      )}

      <button className="btn" onClick={clearSelection} style={{ marginTop: "var(--s-2)" }}>
        Clear Selection
      </button>
    </div>
  );
}

function PropertiesTab() {
  const { workspace, setMode } = useWorkspace();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", padding: "var(--s-1) 0", textAlign: "center" }}>
        Select an artifact or version to view its properties.
      </div>
      {workspace.versionIds.length >= 2 && (
        <button
          className="btn btn-primary"
          onClick={() => setMode("compare")}
          style={{ width: "100%" }}
        >
          Compare Versions
        </button>
      )}
    </div>
  );
}

function InsightsTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div className="section-label" style={{ margin: 0 }}>Analysis</div>
      <div className="stat-grid">
        <div className="stat">
          <span className="s-label">Key</span>
          <span className="s-value">C major</span>
        </div>
        <div className="stat">
          <span className="s-label">Tempo</span>
          <span className="s-value">120 BPM</span>
        </div>
        <div className="stat">
          <span className="s-label">Time Signature</span>
          <span className="s-value">4/4</span>
        </div>
        <div className="stat">
          <span className="s-label">Chords</span>
          <span className="s-value">I-IV-V-vi</span>
        </div>
      </div>
    </div>
  );
}

function AITab() {
  return <MusicChat />;
}
