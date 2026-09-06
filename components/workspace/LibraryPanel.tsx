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
import styles from "./LibraryPanel.module.css";

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
    <div className={`${styles.row}${selected ? ` ${styles.selected}` : ""}`}>
      <button
        type="button"
        className={styles.rowButton}
        onClick={onOpen}
        onPointerEnter={schedulePointerPrefetch}
        onPointerLeave={cancelPointerPrefetch}
        onFocus={prefetchImmediately}
        aria-current={selected ? "true" : undefined}
        disabled={isDeleting}
      >
        {(isLoading || isDeleting) && <span className={styles.spinner} aria-hidden="true" />}
        <span className={styles.copy}>
          <span className={styles.title}>{title}</span>
          {status && <span className={styles.status}>{status}</span>}
        </span>
      </button>

      <Tooltip content="Delete recording" placement="left">
        <IconButton
          className={styles.rowAction}
          compact
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
        className={`studio-library studio-library-v3 ${styles.panel}${workspace.libraryCollapsed ? " is-collapsed" : ""}`}
        aria-hidden={workspace.libraryCollapsed}
        inert={workspace.libraryCollapsed}
      >
        <div className={styles.header}>
          <div className={styles.headingRow}>
            <h2>Library</h2>
            {works.length > 0 && <span className={styles.count}>{works.length}</span>}
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
              {importStatus && <span id="library-import-status" className={styles.importStatus} role="status">{importStatus}</span>}
            </>
          )}
        </div>

        <div className={styles.list}>
          {deleteError && <InlineNotice tone="danger" role="alert">{deleteError}</InlineNotice>}
          {works.length === 0 && libraryLoading ? (
            <div className={styles.loadingList} aria-hidden="true"><span /><span /><span /></div>
          ) : works.length === 0 ? (
            <div className={styles.empty}>
              <strong>No recordings yet</strong>
              <p>Import a recording to begin.</p>
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

        <div className={styles.footer}>
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
