"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useWorkspace, type TranscriptionProfile } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import {
  useDeleteWorkMutation,
  useLibraryProject,
  useProjectWorks,
} from "@/lib/server-state";
import { presentableTitle } from "@/lib/format";
import { deriveAvailability } from "@/lib/representation-availability";

function WorkRow({
  work,
  selected,
  isLoading,
  isDeleting,
  hasAnalysis,
  hasRepresentations,
  onDelete,
  onOpen,
}: {
  work: { id: string; title: string };
  selected: boolean;
  isLoading: boolean;
  isDeleting: boolean;
  hasAnalysis: boolean;
  hasRepresentations: boolean;
  onDelete: () => void;
  onOpen: () => void;
}) {
  const title = presentableTitle(work.title);
  const status = isDeleting
    ? "Deleting"
    : isLoading
      ? "Opening"
      : hasAnalysis
        ? "Analyzed"
        : hasRepresentations
          ? "Ready"
          : "Imported";

  return (
    <div className={`library-work-row${selected ? " selected" : ""}`}>
      <button
        type="button"
        className="library-work-btn"
        onClick={onOpen}
        aria-current={selected ? "true" : undefined}
        disabled={isDeleting}
      >
        <span className="library-work-leading" aria-hidden="true">
          {isLoading || isDeleting ? <span className="library-row-spinner" /> : <span className="library-note-glyph">♪</span>}
        </span>
        <span className="library-work-copy">
          <span className="library-work-title">{title}</span>
          <span className="library-work-status">{status}</span>
        </span>
      </button>

      <button
        type="button"
        className="library-row-delete"
        aria-label={`Delete ${title}`}
        title="Delete recording"
        onClick={onDelete}
        disabled={isDeleting}
      >
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3.5 4.5h9" />
          <path d="M6 2.75h4" />
          <path d="M5 4.5l.5 8.25h5l.5-8.25" />
          <path d="M7 6.5v4M9 6.5v4" />
        </svg>
      </button>
    </div>
  );
}

function ImportSettings({
  profile,
  onChange,
}: {
  profile: TranscriptionProfile;
  onChange: (profile: TranscriptionProfile) => void;
}) {
  return (
    <details className="library-import-settings">
      <summary>Transcription · {profile === "solo_piano" ? "Solo piano" : "Auto"}</summary>
      <div className="library-import-settings-body" role="group" aria-label="Transcription mode">
        <button type="button" className={profile === "auto" ? "active" : ""} aria-pressed={profile === "auto"} onClick={() => onChange("auto")}>Auto</button>
        <button type="button" className={profile === "solo_piano" ? "active" : ""} aria-pressed={profile === "solo_piano"} onClick={() => onChange("solo_piano")}>Solo piano</button>
      </div>
    </details>
  );
}

export default function LibraryPanel({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { user } = useAuth();
  const {
    workspace,
    requestImport,
    setActiveWorkId,
    clearSelection,
    setTranscriptionProfile,
  } = useWorkspace();
  const { clearActiveSource } = useTransport();
  const { resetTimeline } = useTimeline();
  const projectQuery = useLibraryProject(signedIn ? user?.id ?? "" : "");
  const project = projectQuery.data;
  const worksQuery = useProjectWorks(project?.id ?? "");
  const works = worksQuery.data ?? [];
  const deleteWorkMutation = useDeleteWorkMutation(project?.id ?? "");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const importReady = canImport && Boolean(project);
  const libraryLoading = signedIn && (projectQuery.isPending || (Boolean(project) && worksQuery.isPending));
  const importStatus = !canImport
    ? "Audio processing is offline"
    : projectQuery.isPending
      ? "Preparing your library"
      : !project
        ? "Library unavailable"
        : null;
  const importStatusId = importStatus ? "library-import-status" : undefined;

  async function signOut() {
    await supabase?.auth.signOut();
    window.location.reload();
  }

  async function handleDelete(workId: string) {
    if (deletingId || !project) return;
    const deletingActiveWork = workspace.activeWorkId === workId;
    setDeletingId(workId);
    setDeleteError(null);
    if (deletingActiveWork) {
      clearActiveSource();
      resetTimeline();
      setActiveWorkId(null);
    }
    clearSelection();
    try {
      await deleteWorkMutation.mutateAsync(workId);
    } catch {
      if (deletingActiveWork) setActiveWorkId(workId);
      setDeleteError("Delete failed. The recording was restored.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <aside
      className={`studio-library studio-library-v3${workspace.libraryCollapsed ? " is-collapsed" : ""}`}
      aria-hidden={workspace.libraryCollapsed}
      inert={workspace.libraryCollapsed}
    >
      <div className="library-header library-header-v3">
        <div className="library-heading-row">
          <h2>Library</h2>
          {works.length > 0 && <span className="library-count">{works.length}</span>}
        </div>
        {signedIn && (
          <>
            <button
              type="button"
              className="library-import-btn"
              onClick={requestImport}
              disabled={!importReady}
              aria-label="Import audio"
              aria-busy={projectQuery.isPending || undefined}
              aria-describedby={importStatusId}
              title={importStatus ?? "Import audio"}
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
                <path d="M7.5 2v11M2 7.5h11" />
              </svg>
              <span>Import audio</span>
            </button>
            {importStatus && <span id="library-import-status" className="library-import-status" role="status">{importStatus}</span>}
            <ImportSettings profile={workspace.transcriptionProfile} onChange={setTranscriptionProfile} />
          </>
        )}
      </div>

      <div className="library-list library-list-v3">
        {deleteError && <div role="alert" className="library-error">{deleteError}</div>}
        {works.length === 0 && libraryLoading ? (
          <div className="library-loading-list" aria-hidden="true">
            <span /><span /><span />
          </div>
        ) : works.length === 0 ? (
          <div className="library-empty library-empty-v3">
            <strong>No recordings yet</strong>
            <p>Import audio to begin.</p>
          </div>
        ) : works.map((work) => {
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
              isDeleting={deletingId === work.id}
              hasAnalysis={workspace.insights.length > 0 && selected}
              hasRepresentations={availability ? availability.availableKinds.length > 0 : false}
              onDelete={() => void handleDelete(work.id)}
              onOpen={() => {
                if (!selected) clearActiveSource();
                setActiveWorkId(work.id);
              }}
            />
          );
        })}
      </div>

      <div className="library-footer library-footer-v3">
        {signedIn && (
          <button type="button" className="library-account-action" onClick={signOut}>
            Sign out
          </button>
        )}
      </div>
    </aside>
  );
}
