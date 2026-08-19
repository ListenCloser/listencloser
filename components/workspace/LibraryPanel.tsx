"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { deleteWork } from "@/lib/api-client";
import { presentableTitle } from "@/lib/format";
import { deriveAvailability } from "@/lib/representation-availability";

export default function LibraryPanel({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const {
    workspace,
    requestImport,
    setActiveWorkId,
    toggleLibrary,
    removeWork,
    restoreWork,
    clearSelection,
  } = useWorkspace();
  const { clearActiveSource } = useTransport();
  const { resetTimeline } = useTimeline();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function signOut() {
    await supabase?.auth.signOut();
    window.location.reload();
  }

  async function handleDelete(workId: string) {
    if (confirmId !== workId) {
      setConfirmId(workId);
      setDeleteError(null);
      return;
    }
    const removed = workspace.works.find((work) => work.id === workId);
    setDeletingId(workId);
    setConfirmId(null);
    setDeleteError(null);
    // Optimistic: the work leaves the library and workspace state immediately.
    // If it was the active work, stop any playback and clear the transport,
    // playhead, duration, and selection so no stale time survives the delete.
    if (workspace.activeWorkId === workId) {
      clearActiveSource();
      resetTimeline();
    }
    removeWork(workId);
    clearSelection();
    try {
      await deleteWork(workId);
    } catch {
      // Backend deletion failed: put the work back and let the user retry.
      if (removed) restoreWork(removed);
      setDeleteError("That work could not be deleted. It has been restored.");
    } finally {
      setDeletingId(null);
    }
  }

  if (workspace.libraryCollapsed) {
    return (
      <aside className="studio-library studio-library-collapsed" style={{ width: 44, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", padding: "var(--s-2) 0", textAlign: "center" }}>
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Expand library">▸</button>
      </aside>
    );
  }

  return (
    <aside className="studio-library" style={{ width: 260, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "var(--s-3)", borderBottom: "1px solid var(--border)" }}>
        <div>
          <div className="section-label" style={{ margin: 0 }}>Your music</div>
          <div style={{ fontSize: "var(--fs-sm)", marginTop: 4 }}>{workspace.works.length} piece{workspace.works.length !== 1 ? "s" : ""}</div>
        </div>
      </div>

      {signedIn && (
        <div style={{ padding: "var(--s-3)", borderBottom: "1px solid var(--border)" }}>
          <button type="button" className="btn btn-primary" style={{ width: "100%" }} onClick={requestImport} disabled={!canImport}>
            {canImport ? "Import audio" : "Import unavailable"}
          </button>
        </div>
      )}

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-2)" }}>
        {deleteError && (
          <div role="alert" style={{ margin: "var(--s-2)", padding: "var(--s-2) var(--s-3)", fontSize: "var(--fs-xs)", lineHeight: 1.45, color: "var(--danger)", background: "var(--danger-soft)", border: "1px solid var(--danger)", borderRadius: "var(--r-md)" }}>
            {deleteError}
          </div>
        )}
        {workspace.works.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", lineHeight: 1.5, padding: "var(--s-2)" }}>
            Imported works will appear here and can be reopened in later sessions.
          </p>
        ) : workspace.works.map((work) => {
          const selected = workspace.activeWorkId === work.id;
          return (
            <div key={work.id} style={{ position: "relative", marginBottom: "var(--s-1)" }}>
              <button type="button"
                onClick={() => {
                  if (!selected) clearActiveSource();
                  setActiveWorkId(work.id);
                }}
                aria-current={selected ? "true" : undefined}
                disabled={workspace.isLoadingWork && selected}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 3,
                  width: "100%",
                  padding: "var(--s-3)",
                  paddingRight: 40,
                  border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
                  borderRadius: "var(--r-md)",
                  background: selected ? "var(--accent-soft)" : "transparent",
                  color: selected ? "var(--text)" : "var(--text)",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "inherit",
                }}
              >
                <span style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-medium)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%" }}>
                  {presentableTitle(work.title)}
                </span>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", display: "flex", justifyContent: "space-between", width: "100%" }}>
                  <span>{new Date(work.created_at).toLocaleDateString()}</span>
                  <span>{workspace.isLoadingWork && selected ? "Loading…" : selected && deriveAvailability(workspace.representations, workspace.insights.length).availableKinds.length ? "Ready" : "Saved"}</span>
                </span>
              </button>
              <button
                title={confirmId === work.id ? "Click again to confirm delete" : "Delete work"}
                onClick={(e) => { e.stopPropagation(); void handleDelete(work.id); }}
                disabled={deletingId === work.id}
                style={{
                  position: "absolute",
                  top: "var(--s-2)",
                  right: "var(--s-2)",
                  width: 30,
                  height: 30,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "none",
                  borderRadius: "var(--r-sm)",
                  background: confirmId === work.id ? "var(--danger-soft)" : "transparent",
                  color: confirmId === work.id ? "var(--danger)" : "var(--muted)",
                  cursor: "pointer",
                  fontSize: 12,
                  padding: 0,
                  opacity: confirmId === work.id ? 1 : 0.75,
                }}
              >
                {deletingId === work.id ? "…" : confirmId === work.id ? "🗑" : "×"}
              </button>
            </div>
          );
        })}
      </div>

      <div style={{ padding: "var(--s-3)", borderTop: "1px solid var(--border)" }}>
        {signedIn ? (
          <button type="button" className="btn" style={{ width: "100%" }} onClick={signOut}>
            Sign out
          </button>
        ) : (
          <p style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", lineHeight: 1.5, margin: 0 }}>
            Sign in to create a private music workspace.
          </p>
        )}
      </div>
    </aside>
  );
}
