"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { deleteWork } from "@/lib/api-client";
import { presentableTitle } from "@/lib/format";
import { deriveAvailability } from "@/lib/representation-availability";

function WorkRow({
  work,
  selected,
  isLoading,
  hasAnalysis,
  hasRepresentations,
  onDelete,
  onOpen,
}: {
  work: { id: string; title: string };
  selected: boolean;
  isLoading: boolean;
  hasAnalysis: boolean;
  hasRepresentations: boolean;
  onDelete: () => void;
  onOpen: () => void;
}) {
  const [confirming, setConfirming] = useState(false);

  const status = isLoading
    ? "Processing"
    : hasRepresentations
      ? "Ready"
      : "Saved";

  const handleDelete = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    onDelete();
  };

  return (
    <div className="library-work-row">
      <button
        type="button"
        className="library-work-btn"
        onClick={onOpen}
        aria-current={selected ? "true" : undefined}
        disabled={isLoading && selected}
      >
        <span className="library-work-title">{presentableTitle(work.title)}</span>
        <span className="library-work-status">
          <span className={`library-status-dot ${isLoading ? "processing" : hasRepresentations ? "ready" : "saved"}`} />
          {status}
          {hasAnalysis && <span className="library-analysis-badge">Analysis</span>}
        </span>
      </button>
      <button
        type="button"
        className={`library-delete-btn${confirming ? " confirming" : ""}`}
        onClick={(e) => { e.stopPropagation(); handleDelete(); }}
        onBlur={() => setConfirming(false)}
        title={confirming ? "Click again to confirm delete" : "Delete work"}
        aria-label={confirming ? "Confirm delete" : "Delete work"}
      >
        {confirming ? "🗑" : "×"}
      </button>
    </div>
  );
}

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
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function signOut() {
    await supabase?.auth.signOut();
    window.location.reload();
  }

  async function handleDelete(workId: string) {
    const removed = workspace.works.find((work) => work.id === workId);
    setDeletingId(workId);
    setDeleteError(null);
    // Optimistic: the work leaves the library and workspace state immediately.
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
      <aside className="studio-library studio-library-collapsed">
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Expand library">▸</button>
      </aside>
    );
  }

  return (
    <aside className="studio-library">
      <div className="library-header">
        <div className="library-header-text">
          <div className="section-label" style={{ margin: 0 }}>Your music</div>
          <div className="library-count">{workspace.works.length} piece{workspace.works.length !== 1 ? "s" : ""}</div>
        </div>
      </div>

      {signedIn && (
        <div className="library-import">
          <button type="button" className="btn btn-primary" style={{ width: "100%" }} onClick={requestImport} disabled={!canImport}>
            {canImport ? "Import audio" : "Import unavailable"}
          </button>
        </div>
      )}

      <div className="library-list">
        {deleteError && (
          <div role="alert" className="library-error">
            {deleteError}
          </div>
        )}
        {workspace.works.length === 0 ? (
          <div className="library-empty">
            <p>Bring in a recording to transcribe, explore, and analyze.</p>
          </div>
        ) : workspace.works.map((work) => {
          const selected = workspace.activeWorkId === work.id;
          const availability = selected
            ? deriveAvailability(workspace.representations, workspace.insights.length)
            : null;
          return (
            <WorkRow
              key={work.id}
              work={work}
              selected={selected}
              isLoading={workspace.isLoadingWork && selected}
              hasAnalysis={workspace.insights.length > 0 && selected}
              hasRepresentations={availability ? availability.availableKinds.length > 0 : false}
              onDelete={() => handleDelete(work.id)}
              onOpen={() => {
                if (!selected) clearActiveSource();
                setActiveWorkId(work.id);
              }}
            />
          );
        })}
      </div>

      <div className="library-footer">
        {signedIn ? (
          <button type="button" className="btn" style={{ width: "100%" }} onClick={signOut}>
            Sign out
          </button>
        ) : (
          <p className="library-signin-hint">
            Sign in to create a private music workspace.
          </p>
        )}
      </div>
    </aside>
  );
}
