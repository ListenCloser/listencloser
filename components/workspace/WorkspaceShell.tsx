"use client";

import { useState, useCallback, useEffect, type ReactNode } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { SelectionProvider } from "@/lib/stores/selection";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace, type WorkspaceMode } from "@/lib/stores/workspace";
import { useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import type { Entity } from "@/lib/domain.types";
import TransportBar from "./TransportBar";
import LibraryPanel from "./LibraryPanel";
import RepresentationStack from "./RepresentationStack";
import InspectorPanel from "./InspectorPanel";
import ComparePanel from "./ComparePanel";

const MODES: { id: WorkspaceMode; label: string }[] = [
  { id: "explore", label: "Explore" },
  { id: "compare", label: "Compare" },
  { id: "correct", label: "Correct" },
];

type VersionInfo = { id: string; label: string; entities: Entity[] };

function WorkspaceContent({
  projectName,
  versions,
  onSignIn,
  onSignOut,
}: {
  projectName?: string;
  versions: VersionInfo[];
  onSignIn: () => void;
  onSignOut: () => void;
}) {
  const { workspace, toggleInspector, setMode } = useWorkspace();
  const { user } = useAuth();
  const [correctedNotes, setCorrectedNotes] = useState<any>(null);

  const compareA = versions.length >= 2 ? versions[versions.length - 2] : null;
  const compareB = versions.length >= 2 ? versions[versions.length - 1] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg)", color: "var(--text)", fontFamily: "var(--font-sans)", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-4)", padding: "var(--s-2) var(--s-4)", background: "var(--panel)", borderBottom: "1px solid var(--border)", minHeight: 44 }}>
        <div className="brand" style={{ fontSize: "var(--fs-sm)", flexShrink: 0 }}>
          <span className="brand-dot" />{projectName || "hello-ai"}
        </div>

        <div style={{ display: "flex", gap: "var(--s-1)" }}>
          {MODES.map((m) => (
            <button key={m.id} onClick={() => setMode(m.id)}
              style={{
                padding: "4px 14px", borderRadius: "var(--r-full)",
                border: workspace.mode === m.id ? "1px solid var(--accent)" : "1px solid transparent",
                background: workspace.mode === m.id ? "var(--accent-soft)" : "transparent",
                color: workspace.mode === m.id ? "var(--accent)" : "var(--muted)",
                fontSize: "var(--fs-xs)", fontWeight: "var(--fw-medium)", cursor: "pointer", fontFamily: "inherit",
                transition: "all var(--dur) var(--ease)",
              }}>
              {m.label}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {user ? (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", fontSize: "var(--fs-xs)" }}>
            <span style={{ color: "var(--muted)" }}>{user.email}</span>
            <button onClick={onSignOut} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "var(--fs-xs)", fontFamily: "inherit" }}>Sign out</button>
          </div>
        ) : (
          <button onClick={onSignIn} style={{ background: "var(--accent)", border: "none", color: "#fff", cursor: "pointer", fontSize: "var(--fs-xs)", fontFamily: "inherit", padding: "4px 14px", borderRadius: "var(--r-full)", fontWeight: "var(--fw-medium)" }}>Sign in</button>
        )}
      </div>

      <TransportBar />

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={!!user} />

        {workspace.mode === "compare" && compareA && compareB ? (
          <ComparePanel versionA={compareA} versionB={compareB} onSelectVersionA={() => {}} onSelectVersionB={() => {}} diffNotes={null} />
        ) : (
          <RepresentationStack mode={workspace.mode} />
        )}

        <InspectorPanel />
      </div>
    </div>
  );
}

export default function WorkspaceShell({
  projectName, versions, children, onSignIn, onSignOut,
}: {
  projectName?: string;
  versions?: VersionInfo[];
  children?: ReactNode;
  onSignIn?: () => void;
  onSignOut?: () => void;
}) {
  return (
    <TransportProvider>
      <SelectionProvider>
        <TimelineProvider>
          <WorkspaceProvider>
            {children}
            <WorkspaceContent projectName={projectName} versions={versions || []}
              onSignIn={onSignIn || (() => {})} onSignOut={onSignOut || (() => {})} />
          </WorkspaceProvider>
        </TimelineProvider>
      </SelectionProvider>
    </TransportProvider>
  );
}
