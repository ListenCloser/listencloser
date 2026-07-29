"use client";

import { useState } from "react";
import { useSelection } from "@/lib/stores/selection";
import { useWorkspace } from "@/lib/stores/workspace";
import MusicChat from "@/components/MusicChat";

type TabId = "selection" | "properties" | "insights" | "ai";

export default function InspectorPanel() {
  const [tab, setTab] = useState<TabId>("selection");
  const { selection } = useSelection();
  const { workspace, toggleInspector } = useWorkspace();

  const hasSelection = selection.timeStart !== null || selection.beatStart !== null;

  return (
    <div style={{ width: "var(--shell-sidebar, 300px)", flexShrink: 0, background: "var(--panel)", borderLeft: "1px solid var(--border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid var(--border)" }}>
        {(["selection", "properties", "ai"] as TabId[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1,
              padding: "var(--s-2) var(--s-3)",
              fontSize: "var(--fs-xs)",
              fontWeight: "var(--fw-medium)",
              border: "none",
              borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
              background: "none",
              color: tab === t ? "var(--text)" : "var(--muted)",
              cursor: "pointer",
              fontFamily: "inherit",
              textTransform: "capitalize",
            }}
          >
            {t}
          </button>
        ))}
        <button onClick={toggleInspector} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 12, padding: "var(--s-2) var(--s-3)", fontFamily: "inherit" }}>✕</button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-3)", fontSize: "var(--fs-sm)" }}>
        {tab === "selection" && (
          hasSelection ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
              {selection.timeStart !== null && (
                <div>
                  <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", marginBottom: 2 }}>Time</div>
                  <div>{selection.timeStart.toFixed(2)}s – {selection.timeEnd?.toFixed(2)}s</div>
                </div>
              )}
              {selection.beatStart !== null && (
                <div>
                  <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", marginBottom: 2 }}>Beats</div>
                  <div>{selection.beatStart.toFixed(1)} – {selection.beatEnd?.toFixed(1)}</div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: "var(--muted)" }}>Click and drag in the piano roll to select a passage.</div>
          )
        )}

        {tab === "properties" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
            <div>
              <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", marginBottom: 2 }}>Project</div>
              <div>{workspace.versionIds?.length || 0} versions</div>
            </div>
            {workspace.midiVersionId && (
              <div>
                <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", marginBottom: 2 }}>Export</div>
                <a href={`/api/v1/versions/${workspace.midiVersionId}/download`} download="transcription.mid" style={{ color: "var(--accent)", textDecoration: "none", fontSize: "var(--fs-xs)" }}>
                  Download MIDI
                </a>
              </div>
            )}
          </div>
        )}

        {tab === "ai" && (
          <div style={{ height: "100%" }}>
            <MusicChat />
          </div>
        )}
      </div>
    </div>
  );
}
