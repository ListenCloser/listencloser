"use client";

import { useState, useCallback, type ReactNode } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { SelectionProvider } from "@/lib/stores/selection";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace, type WorkspaceMode } from "@/lib/stores/workspace";
import { useAuth } from "@/components/AuthProvider";
import { startCompareWorkflow, startCorrectWorkflow, getEntities } from "@/lib/api-client";
import TransportBar from "./TransportBar";
import LibraryPanel from "./LibraryPanel";
import RepresentationStack from "./RepresentationStack";
import InspectorPanel from "./InspectorPanel";
import ComparePanel from "./ComparePanel";
import ProcessingBanner from "./ProcessingBanner";
import type { Job, Entity } from "@/lib/domain.types";

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

function WorkspaceContent({ projectName }: { projectName?: string }) {
  const { workspace, toggleInspector } = useWorkspace();
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [correctedNotes, setCorrectedNotes] = useState<ReturnType<typeof JSON.parse> | null>(null);
  const [compareVersionA, setCompareVersionA] = useState<{ id: string; label: string; entities: Entity[] } | null>(null);
  const [compareVersionB, setCompareVersionB] = useState<{ id: string; label: string; entities: Entity[] } | null>(null);
  const [diffNotes, setDiffNotes] = useState<unknown[] | null>(null);

  const handleCompare = useCallback(async (vidA: string, vidB: string) => {
    const { job } = await startCompareWorkflow(vidA, vidB, "default");
    setJobs((prev) => [...prev, job]);
    const [entitiesA, entitiesB] = await Promise.all([getEntities(vidA), getEntities(vidB)]);
    setCompareVersionA({ id: vidA, label: vidA, entities: entitiesA });
    setCompareVersionB({ id: vidB, label: vidB, entities: entitiesB });
    setDiffNotes(null);
  }, []);

  const handleSaveCorrection = useCallback(async () => {
    if (!workspace.currentVersionId || !correctedNotes) return;
    const { job } = await startCorrectWorkflow(
      workspace.currentVersionId, "default", correctedNotes
    );
    setJobs((prev) => [...prev, job]);
  }, [workspace.currentVersionId, correctedNotes]);

  const handleCancel = useCallback((jobId: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  const handleRetry = useCallback((jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              lifecycle: {
                ...j.lifecycle,
                current: "queued" as const,
                progress: 0,
                message: "Retrying…",
                error: null as string | null,
              },
            }
          : j,
      ),
    );
  }, []);

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

        <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)", display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
          {user ? (
            <>
              <span style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>{user.email}</span>
              <button className="btn" style={{ fontSize: "var(--fs-xs)", padding: "2px 8px" }} onClick={() => { /* sign out handled by parent */ }}>
                Sign out
              </button>
            </>
          ) : (
            <button className="btn btn-primary" style={{ fontSize: "var(--fs-xs)", padding: "4px 12px" }}>
              Sign in
            </button>
          )}
        </div>

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

      {workspace.mode === "correct" && correctedNotes && (
        <div style={{
          display: "flex", alignItems: "center", gap: "var(--s-3)",
          padding: "var(--s-2) var(--s-4)", background: "var(--panel-2)",
          borderBottom: "1px solid var(--border)", fontSize: "var(--fs-xs)",
        }}>
          <span style={{ color: "var(--accent-2)", fontWeight: "var(--fw-medium)" }}>
            Correction mode active — {Array.isArray(correctedNotes) ? correctedNotes.length : 0} notes modified
          </span>
          <div style={{ flex: 1 }} />
          <button className="btn btn-primary" onClick={handleSaveCorrection} style={{ padding: "4px 16px" }}>
            Save Correction
          </button>
        </div>
      )}

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={!!user} />

        {workspace.mode === "compare" ? (
          <ComparePanel
            versionA={compareVersionA}
            versionB={compareVersionB}
            onSelectVersionA={() => {}}
            onSelectVersionB={() => {}}
            diffNotes={diffNotes as any}
            onCompare={handleCompare}
          />
        ) : (
          <RepresentationStack
            mode={workspace.mode}
            correctedNotes={correctedNotes as any}
            onCorrectedNotesChange={workspace.mode === "correct" ? setCorrectedNotes : undefined}
          />
        )}

        <InspectorPanel />
      </div>

      <ProcessingBanner
        jobs={jobs}
        onCancel={handleCancel}
        onRetry={handleRetry}
      />
    </div>
  );
}

export default function WorkspaceShell({
  projectName,
  children,
}: {
  projectName?: string;
  children?: ReactNode;
}) {
  return (
    <TransportProvider>
      <SelectionProvider>
        <TimelineProvider>
          <WorkspaceProvider>
            {children}
            <WorkspaceContent projectName={projectName} />
          </WorkspaceProvider>
        </TimelineProvider>
      </SelectionProvider>
    </TransportProvider>
  );
}
