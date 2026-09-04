"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/AuthProvider";
import Tooltip from "@/components/ui/Tooltip";
import LibraryImportControl from "@/components/workspace/LibraryImportControl";
import PitchContourProcessing from "@/components/workspace/PitchContourProcessing";
import { getWorkBundle, startUnderstandWorkflow, uploadArtifact } from "@/lib/api-client";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import {
  refreshProjectWorks,
  useDeleteWorkMutation,
  useLibraryProject,
  useProjectWorks,
} from "@/lib/server-state";
import { downloadPublicRecording, type PublicRecording } from "@/lib/public-recordings";
import { presentableTitle } from "@/lib/format";
import { successorAfterDelete } from "@/lib/work-selection";

const POINTER_PREFETCH_DELAY_MS = 120;

export function WorkRow({
  work,
  selected,
  isLoading,
  isDeleting,
  onDelete,
  onOpen,
  onPrefetch,
}: {
  work: { id: string; title: string };
  selected: boolean;
  isLoading: boolean;
  isDeleting: boolean;
  onDelete: () => void;
  onOpen: () => void;
  onPrefetch: () => void;
}) {
  const title = presentableTitle(work.title);
  const pointerPrefetchRef = useRef<number | null>(null);
  // A library row describes durable availability, not whatever part of the
  // selected work happens to have hydrated into the workspace store. The old
  // Imported/Ready/Analyzed labels therefore changed as you clicked between
  // rows even though nothing about the saved recording had changed.
  const status = isDeleting ? "Deleting" : isLoading ? "Opening" : "Ready";

  const cancelPointerPrefetch = () => {
    if (pointerPrefetchRef.current === null) return;
    window.clearTimeout(pointerPrefetchRef.current);
    pointerPrefetchRef.current = null;
  };

  const prefetchImmediately = () => {
    cancelPointerPrefetch();
    if (!selected && !isDeleting) onPrefetch();
  };

  const schedulePointerPrefetch = () => {
    if (selected || isDeleting || pointerPrefetchRef.current !== null) return;
    pointerPrefetchRef.current = window.setTimeout(() => {
      pointerPrefetchRef.current = null;
      onPrefetch();
    }, POINTER_PREFETCH_DELAY_MS);
  };

  useEffect(() => cancelPointerPrefetch, []);

  return (
    <div className={`library-work-row${selected ? " selected" : ""}`}>
      <button
        type="button"
        className="library-work-btn"
        onClick={onOpen}
        onPointerEnter={schedulePointerPrefetch}
        onPointerLeave={cancelPointerPrefetch}
        onFocus={prefetchImmediately}
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

      <Tooltip content="Delete recording" placement="left">
        <button
          type="button"
          className="library-row-delete"
          aria-label={`Delete ${title}`}
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
      </Tooltip>
    </div>
  );
}

function ImportSettings() {
  const {
    workspace,
    requestScoreEngine,
    setScoreEngine,
    setTranscriptionProfile,
  } = useWorkspace();
  const activeScore = workspace.representations.find((representation) => representation.kind === "score");
  const hasPerformanceMidi = workspace.representations.some((representation) => representation.kind === "piano_roll");
  const selectedEngineLabel = workspace.scoreEngine === "pm2s" ? "PM2S" : "MuseScore";
  const activeScoreMatchesSelection = Boolean(
    activeScore && (
      workspace.scoreEngine === "pm2s"
        ? activeScore.provenance.startsWith("PM2S")
        : !activeScore.provenance.startsWith("PM2S")
    ),
  );
  const canGenerateScore = Boolean(
    workspace.activeWorkId
    && !workspace.isLoadingWork
    && (hasPerformanceMidi || activeScore)
    && !activeScoreMatchesSelection,
  );

  return (
    <details className="library-import-settings">
      <summary>Processing</summary>
      <div style={{ display: "grid", gap: "var(--s-3)", paddingTop: "var(--s-2)" }}>
        <div style={{ display: "grid", gap: "6px" }}>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Transcription</span>
          <div className="library-import-settings-body" role="group" aria-label="Transcription mode">
            <Tooltip stretch content="General and mixed recordings">
              <button
                type="button"
                className={workspace.transcriptionProfile === "auto" ? "active" : ""}
                aria-pressed={workspace.transcriptionProfile === "auto"}
                onClick={() => setTranscriptionProfile("auto")}
              >
                Auto
              </button>
            </Tooltip>
            <Tooltip stretch content="Best measured transcription for known solo piano">
              <button
                type="button"
                className={workspace.transcriptionProfile === "solo_piano" ? "active" : ""}
                aria-pressed={workspace.transcriptionProfile === "solo_piano"}
                onClick={() => setTranscriptionProfile("solo_piano")}
              >
                Solo piano
              </button>
            </Tooltip>
          </div>
        </div>

        <div style={{ display: "grid", gap: "6px" }}>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Score reconstruction</span>
          <div className="library-import-settings-body" role="group" aria-label="Score reconstruction engine">
            <Tooltip stretch content="Current notation baseline">
              <button
                type="button"
                className={workspace.scoreEngine === "musescore" ? "active" : ""}
                aria-pressed={workspace.scoreEngine === "musescore"}
                onClick={() => setScoreEngine("musescore")}
              >
                MuseScore
              </button>
            </Tooltip>
            <Tooltip stretch content="Experimental learned piano score reconstruction">
              <button
                type="button"
                className={workspace.scoreEngine === "pm2s" ? "active" : ""}
                aria-pressed={workspace.scoreEngine === "pm2s"}
                onClick={() => setScoreEngine("pm2s")}
              >
                PM2S
              </button>
            </Tooltip>
          </div>
        </div>

        {workspace.activeWorkId && (
          <div style={{ display: "grid", gap: "6px" }}>
            <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Current score source</span>
            <span style={{ fontSize: "var(--fs-xs)" }}>
              {activeScore?.provenance ?? `No ${selectedEngineLabel} score generated yet`}
            </span>
            <button
              type="button"
              className="btn btn-sm"
              disabled={!canGenerateScore}
              onClick={() => requestScoreEngine(workspace.scoreEngine)}
            >
              {activeScoreMatchesSelection ? `${selectedEngineLabel} score ready` : `Generate ${selectedEngineLabel} score`}
            </button>
            <span className="muted" style={{ fontSize: "var(--fs-xs)", lineHeight: 1.35 }}>
              {activeScoreMatchesSelection
                ? "Select another engine to generate an alternate Score from the same performance MIDI."
                : "Generation reuses this recording's performance MIDI; transcription is not rerun."}
            </span>
          </div>
        )}
        {workspace.activeWorkId && <PitchContourProcessing />}
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
  } = useWorkspace();
  const { clearActiveSource } = useTransport();
  const { resetTimeline } = useTimeline();
  const queryClient = useQueryClient();
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

  async function handlePublicImport(recording: PublicRecording) {
    if (!project) throw new Error("Your library is still loading.");
    if (!canImport) throw new Error("Audio processing is temporarily unavailable.");

    // Resolve and download only allowlisted Commons catalog entries. The file
    // then crosses the exact same signed-upload durability boundary as a local
    // recording; there is no separate demo/sample persistence path.
    const file = await downloadPublicRecording(recording);
    const { artifact, version } = await uploadArtifact(project.id, file);
    await refreshProjectWorks(queryClient, project.id);

    try {
      await startUnderstandWorkflow(
        version.id,
        project.id,
        workspace.transcriptionProfile,
        workspace.scoreEngine,
      );
    } catch (cause) {
      // Upload durability still wins if enrichment dispatch fails. Open the
      // saved Work so the user can see/retry it through the normal product path.
      setActiveWorkId(artifact.work_id);
      const detail = cause instanceof Error ? `: ${cause.message}` : ".";
      throw new Error(`Recording saved, but processing could not start${detail}`);
    }

    setActiveWorkId(artifact.work_id);
  }

  async function handleDelete(workId: string) {
    if (deletingId || !project) return;
    const deletingActiveWork = workspace.activeWorkId === workId;
    const successor = successorAfterDelete(works, workId);
    setDeletingId(workId);
    setDeleteError(null);
    if (deletingActiveWork) {
      clearActiveSource();
      resetTimeline();
      clearSelection();
      // A non-empty durable library should transition directly to another
      // recording. Never create a transient first-run/empty-library state just
      // because the selected row is being deleted.
      setActiveWorkId(successor?.id ?? null);
    }
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
            <LibraryImportControl
              disabled={!importReady}
              busy={projectQuery.isPending}
              statusId={importStatusId}
              onUpload={requestImport}
              onImport={handlePublicImport}
            />
            {importStatus && <span id="library-import-status" className="library-import-status" role="status">{importStatus}</span>}
            <ImportSettings />
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
            <p>Upload or choose a public recording to begin.</p>
          </div>
        ) : works.map((work) => {
          const selected = workspace.activeWorkId === work.id;
          return (
            <WorkRow
              key={work.id}
              work={work}
              selected={selected}
              isLoading={workspace.isLoadingWork && selected}
              isDeleting={deletingId === work.id}
              onDelete={() => void handleDelete(work.id)}
              onPrefetch={() => {
                // Intent prefetch is deliberately bounded to one hovered or
                // keyboard-focused row. The revisioned Work cache deduplicates
                // this request with the eventual click/load path.
                void getWorkBundle(work.id).catch(() => undefined);
              }}
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
