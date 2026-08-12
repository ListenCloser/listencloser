"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { useTransport } from "@/lib/stores/transport";
import { deleteWork } from "@/lib/api-client";
import { deriveAvailability } from "@/lib/representation-availability";

export default function LibraryPanel({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const {
    workspace,
    requestImport,
    setActiveWorkId,
    toggleLibrary,
    removeWork,
  } = useWorkspace();
  const { clearActiveSource } = useTransport();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  async function signOut() {
    await supabase?.auth.signOut();
    window.location.reload();
  }

  async function handleDelete(workId: string, title: string) {
    if (confirmId !== workId) {
      setConfirmId(workId);
      return;
    }
    setDeletingId(workId);
    try {
      if (workspace.activeWorkId === workId) {
        clearActiveSource();
        setActiveWorkId(null);
      }
      await deleteWork(workId);
      removeWork(workId);
    } catch {
      setConfirmId(null);
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
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Collapse library">◂</button>
      </div>

      {signedIn && (
        <div style={{ padding: "var(--s-3)", borderBottom: "1px solid var(--border)" }}>
          <button type="button" className="btn btn-primary" style={{ width: "100%" }} onClick={requestImport} disabled={!canImport}>
            {canImport ? "Import audio" : "Import unavailable"}
          </button>
        </div>
      )}

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-2)" }}>
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
                  paddingRight: 32,
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
                  {work.title}
                </span>
                <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", display: "flex", justifyContent: "space-between", width: "100%" }}>
                  <span>{new Date(work.created_at).toLocaleDateString()}</span>
                  <span>{workspace.isLoadingWork && selected ? "Loading…" : selected && deriveAvailability(workspace.representations, workspace.insights.length).availableKinds.length ? "Ready" : "Saved"}</span>
                </span>
              </button>
              <button
                title={confirmId === work.id ? "Click again to confirm delete" : "Delete work"}
                onClick={(e) => { e.stopPropagation(); handleDelete(work.id, work.title); }}
                disabled={deletingId === work.id}
                style={{
                  position: "absolute",
                  top: "var(--s-2)",
                  right: "var(--s-2)",
                  width: 20,
                  height: 20,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "none",
                  borderRadius: "var(--r-sm)",
                  background: confirmId === work.id ? "var(--danger-soft)" : "transparent",
                  color: confirmId === work.id ? "var(--danger)" : "var(--muted)",
                  cursor: "pointer",
                  fontSize: 10,
                  padding: 0,
                  opacity: 0.6,
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
