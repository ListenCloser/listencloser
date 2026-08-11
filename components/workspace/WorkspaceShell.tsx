"use client";

import { type ReactNode } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { SelectionProvider } from "@/lib/stores/selection";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace, type WorkspaceMode } from "@/lib/stores/workspace";
import TransportBar from "./TransportBar";
import LibraryPanel from "./LibraryPanel";
import RepresentationStack from "./RepresentationStack";
import InspectorPanel from "./InspectorPanel";

const MODES: { id: WorkspaceMode; label: string }[] = [
  { id: "explore", label: "Explore" },
  { id: "compare", label: "Compare" },
  { id: "correct", label: "Correct" },
  { id: "create", label: "Create" },
  { id: "history", label: "History" },
];

function ModeSelector() {
  const { workspace, setMode } = useWorkspace();

  return (
    <div style={{ display: "flex", gap: "var(--s-1)" }}>
      {MODES.map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id)}
          style={{
            padding: "4px 12px",
            borderRadius: "var(--r-full)",
            border: `1px solid ${workspace.mode === m.id ? "transparent" : "var(--border)"}`,
            background:
              workspace.mode === m.id
                ? "var(--accent)"
                : "transparent",
            color:
              workspace.mode === m.id
                ? "var(--bg)"
                : "var(--muted)",
            fontSize: "var(--fs-xs)",
            fontWeight: "var(--fw-medium)",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all var(--dur) var(--ease)",
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

function WorkspaceContent({ signedIn = false, projectName }: { signedIn?: boolean; projectName?: string }) {
  const { workspace, toggleInspector } = useWorkspace();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-4)",
          padding: "var(--s-2) var(--s-4)",
          background: "var(--panel)",
          borderBottom: "1px solid var(--border)",
          minHeight: 44,
        }}
      >
        <div className="brand" style={{ fontSize: "var(--fs-sm)", flexShrink: 0 }}>
          <span className="brand-dot" />
          {projectName || "hello-ai"}
        </div>

        <ModeSelector />

        <div style={{ flex: 1 }} />

        {workspace.inspectorCollapsed && (
          <button
            className="icon-btn ghost"
            onClick={toggleInspector}
            style={{ padding: "4px 10px", fontSize: "var(--fs-xs)" }}
          >
            Inspector
          </button>
        )}
      </div>

      <TransportBar />

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={signedIn} projectName={projectName} />

        <RepresentationStack />

        <InspectorPanel />
      </div>

    </div>
  );
}

export default function WorkspaceShell({
  signedIn = false,
  projectName,
  children,
}: {
  signedIn?: boolean;
  projectName?: string;
  children?: ReactNode;
}) {
  return (
    <TransportProvider>
      <SelectionProvider>
        <TimelineProvider>
          <WorkspaceProvider>
            {children}
            <WorkspaceContent signedIn={signedIn} projectName={projectName} />
          </WorkspaceProvider>
        </TimelineProvider>
      </SelectionProvider>
    </TransportProvider>
  );
}
