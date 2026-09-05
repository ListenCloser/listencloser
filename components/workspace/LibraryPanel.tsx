"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/AuthProvider";
import Button, { IconButton } from "@/components/ui/Button";
import Dialog, { DialogBody, DialogFooter, DialogHeader, DialogHeading } from "@/components/ui/Dialog";
import { CloseIcon, TrashIcon } from "@/components/ui/Icons";
import InlineNotice from "@/components/ui/InlineNotice";
import Tooltip from "@/components/ui/Tooltip";
import LibraryImportControl, { type ImportProcessingConfig } from "@/components/workspace/LibraryImportControl";
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
        <IconButton
          variant="ghost"
          aria-label={`Delete ${title}`}
          onClick={onDelete}
          disabled={isDeleting}
        >
          <TrashIcon />
        </IconButton>
      </Tooltip>
    </div>
  );
}

export default function LibraryPanel({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { user } = useAuth();
  const {
    workspace,
    requestImport,
    setActiveWorkId,
    clearSelection,
    setScoreEngine,
    setTranscriptionProfile,
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
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);
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

  async function handlePublicImport(recording: PublicRecording, processing: ImportProcessingConfig) {
    if (!project) throw new Error("Your library is still loading.");
    if (!canImport) throw new Error("Audio processing is temporarily unavailable.");

    const file = await downloadPublicRecording(recording);
    const { artifact, version } = await uploadArtifact(project.id, file);
    await refreshProjectWorks(queryClient, project.id);

    try {
      await startUnderstandWorkflow(
        version.id,
        project.id,
        processing.transcriptionProfile,
        processing.scoreEngine,
      );
    } catch (cause) {
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
    setDeleteTarget(null);
    setDeleteError(null);
    if (deletingActiveWork) {
      clearActiveSource();
      resetTimeline();
      clearSelection();
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
    <>
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
                transcriptionProfile={workspace.transcriptionProfile}
                scoreEngine={workspace.scoreEngine}
                onTranscriptionProfileChange={setTranscriptionProfile}
                onScoreEngineChange={setScoreEngine}
                onUpload={requestImport}
                onImport={handlePublicImport}
              />
              {importStatus && <span id="library-import-status" className="library-import-status" role="status">{importStatus}</span>}
            </>
          )}
        </div>

        <div className="library-list library-list-v3">
          {deleteError && <InlineNotice tone="danger" role="alert">{deleteError}</InlineNotice>}
          {works.length === 0 && libraryLoading ? (
            <div className="library-loading-list" aria-hidden="true"><span /><span /><span /></div>
          ) : works.length === 0 ? (
            <div className="library-empty library-empty-v3">
              <strong>No recordings yet</strong>
              <p>Upload or choose a public recording to begin.</p>
            </div>
          ) : works.map((work) => {
            const selected = workspace.activeWorkId === work.id;
            const title = presentableTitle(work.title);
            return (
              <WorkRow
                key={work.id}
                work={work}
                selected={selected}
                isLoading={workspace.isLoadingWork && selected}
                isDeleting={deletingId === work.id}
                onDelete={() => setDeleteTarget({ id: work.id, title })}
                onPrefetch={() => { void getWorkBundle(work.id).catch(() => undefined); }}
                onOpen={() => {
                  if (!selected) clearActiveSource();
                  setActiveWorkId(work.id);
                }}
              />
            );
          })}
        </div>

        <div className="library-footer library-footer-v3">
          {signedIn && <Button variant="ghost" fullWidth onClick={signOut}>Sign out</Button>}
        </div>
      </aside>

      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} compact>
        <DialogHeader>
          <DialogHeading
            title="Delete recording?"
            description={deleteTarget ? `This permanently deletes “${deleteTarget.title}” and its generated analysis.` : undefined}
          />
          <IconButton variant="ghost" onClick={() => setDeleteTarget(null)} aria-label="Cancel delete">
            <CloseIcon />
          </IconButton>
        </DialogHeader>
        <DialogBody>
          <InlineNotice tone="quiet">This action cannot be undone.</InlineNotice>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button
            variant="danger"
            onClick={() => {
              if (deleteTarget) void handleDelete(deleteTarget.id);
            }}
          >
            Delete recording
          </Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}
