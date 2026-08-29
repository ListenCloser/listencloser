"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import TabStrip from "@/components/ui/TabStrip";
import { availableRepresentations, type RepresentationId } from "@/lib/representations";
import { useLibraryProject, useProjectWorks } from "@/lib/server-state";
import { useWorkspace, type TranscriptionProfile } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";

const ORIENTATION_CUE_MS = 560;

function TranscriptionModeToggle() {
  const { workspace, setTranscriptionProfile } = useWorkspace();
  const options: { id: TranscriptionProfile; label: string; description: string }[] = [
    { id: "auto", label: "Auto", description: "Best default for most recordings" },
    { id: "solo_piano", label: "Solo piano", description: "Prefer piano-specific transcription" },
  ];
  return (
    <div className="transcription-mode" role="group" aria-label="Transcription mode">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={workspace.transcriptionProfile === option.id}
          className={workspace.transcriptionProfile === option.id ? "active" : ""}
          onClick={() => setTranscriptionProfile(option.id)}
          title={option.description}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function WorkspaceLoadingSkeleton() {
  return (
    <main className="piece-desk piece-loading-shell" aria-busy="true" aria-label="Opening recording">
      <div className="representation-toolbar representation-toolbar-loading" aria-hidden="true">
        <span className="loading-pill loading-pill-wide" />
        <span className="loading-pill" />
        <span className="loading-pill" />
        <span className="loading-pill" />
      </div>
      <div className="piece-loading-canvas" role="status">
        <div className="piece-loading-visual" aria-hidden="true">
          {Array.from({ length: 7 }).map((_, row) => (
            <span key={row} style={{ "--loading-row": row } as React.CSSProperties} />
          ))}
        </div>
        <span className="sr-only">Opening the saved recording.</span>
      </div>
    </main>
  );
}

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { user } = useAuth();
  const { workspace, requestImport, setActiveRepresentation } = useWorkspace();
  const projectQuery = useLibraryProject(signedIn ? user?.id ?? "" : "");
  const projectId = projectQuery.data?.id ?? "";
  const worksQuery = useProjectWorks(projectId);
  const durableWorks = worksQuery.data ?? [];
  const libraryLoading = signedIn && (projectQuery.isPending || (Boolean(projectId) && worksQuery.isPending));
  const librarySettled = signedIn && !projectQuery.isPending && !worksQuery.isPending && !projectQuery.isError && !worksQuery.isError;
  const libraryHasWorks = durableWorks.length > 0;
  const [mountedViews, setMountedViews] = useState<Set<RepresentationId>>(() => new Set());
  const [orientationCue, setOrientationCue] = useState(false);
  const orientationFrame = useRef<number | null>(null);
  const orientationTimeout = useRef<number | null>(null);
  const availability = useMemo(
    () => deriveAvailability(workspace.representations, workspace.insights.length),
    [workspace.representations, workspace.insights.length],
  );
  const available = useMemo(() => availableRepresentations(availability), [availability]);
  const activeView = available.some((view) => view.id === workspace.activeRepresentation)
    ? workspace.activeRepresentation
    : available[0]?.id ?? null;

  useEffect(() => {
    if (available.some((view) => view.id === workspace.activeRepresentation)) return;
    setActiveRepresentation(available[0]?.id ?? null);
  }, [available, setActiveRepresentation, workspace.activeRepresentation]);

  // The shared selection is authoritative. This local cue only strengthens the
  // actual selected destination after Focus/Show and then returns it to quiet.
  useEffect(() => {
    const cancelPendingCue = () => {
      if (orientationFrame.current !== null) {
        window.cancelAnimationFrame(orientationFrame.current);
        orientationFrame.current = null;
      }
      if (orientationTimeout.current !== null) {
        window.clearTimeout(orientationTimeout.current);
        orientationTimeout.current = null;
      }
    };

    const handleOrientation = () => {
      cancelPendingCue();
      setOrientationCue(false);
      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
      orientationFrame.current = window.requestAnimationFrame(() => {
        orientationFrame.current = null;
        setOrientationCue(true);
        orientationTimeout.current = window.setTimeout(() => {
          orientationTimeout.current = null;
          setOrientationCue(false);
        }, ORIENTATION_CUE_MS);
      });
    };

    window.addEventListener(WORKSPACE_ORIENTATION_EVENT, handleOrientation);
    return () => {
      window.removeEventListener(WORKSPACE_ORIENTATION_EVENT, handleOrientation);
      cancelPendingCue();
    };
  }, []);

  // Representation canvases are expensive client-side objects: OSMD builds a
  // full score SVG, WaveSurfer owns waveform state, and the spectrogram decodes
  // audio. Preserve views after their first visit within a work session so a
  // tab switch is a visibility change rather than a destroy/rebuild cycle.
  useEffect(() => {
    setMountedViews(new Set());
    setOrientationCue(false);
  }, [workspace.activeWorkId]);

  useEffect(() => {
    if (!activeView) return;
    setMountedViews((previous) => {
      if (previous.has(activeView)) return previous;
      const next = new Set(previous);
      next.add(activeView);
      return next;
    });
  }, [activeView]);

  if (workspace.isLoadingWork || libraryLoading) return <WorkspaceLoadingSkeleton />;
  if (!available.length || !activeView) {
    // No hydrated representation is not the same thing as an empty library.
    // During selection, deletion recovery, or a transient Work refresh, keep a
    // neutral opening state as long as durable Works still exist. The first-run
    // import CTA is reserved for a settled, genuinely empty library.
    if (libraryHasWorks || !librarySettled) return <WorkspaceLoadingSkeleton />;
    return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;
  }

  const renderedViews = available.filter((definition) => definition.id === activeView || mountedViews.has(definition.id));

  return (
    <main className="piece-desk piece-desk-v3">
      <div className="representation-toolbar">
        <TabStrip
          className="piece-view-tabs piece-view-tabs-v3"
          label="Music representation"
          items={available.map((def) => ({ id: def.id, label: def.title }))}
          value={activeView}
          onChange={setActiveRepresentation}
        />
      </div>

      {renderedViews.map((definition) => {
        const ViewComponent = definition.component;
        const active = definition.id === activeView;
        return (
          <section
            key={definition.id}
            className="piece-active-view piece-active-view-v3"
            aria-label={definition.title}
            aria-hidden={!active}
            hidden={!active}
          >
            <ViewComponent active={active} orientationCue={active && orientationCue} />
          </section>
        );
      })}
    </main>
  );
}

function EmptyDesk({ signedIn, canImport, onImport }: { signedIn: boolean; canImport: boolean; onImport: () => void }) {
  return (
    <main className="piece-desk piece-empty piece-empty-v3">
      <div className="empty-desk-art" aria-hidden="true">
        <span className="empty-staff-line" /><span className="empty-staff-line" /><span className="empty-staff-line" /><span className="empty-staff-line" /><span className="empty-staff-line" />
        <span className="empty-note empty-note-one">♪</span>
        <span className="empty-note empty-note-two">♫</span>
      </div>
      <div className="empty-desk-copy">
        <h1>Import a recording</h1>
        <p>Listen, transcribe, inspect notation, and analyze the same piece in one workspace.</p>
        <button className="btn btn-primary empty-import-primary" onClick={onImport} disabled={!signedIn || !canImport}>
          Import audio
        </button>
        <details className="transcription-settings">
          <summary>Transcription</summary>
          <TranscriptionModeToggle />
        </details>
        <small>WAV, MP3, M4A, FLAC, OGG, AAC · up to 4 MB</small>
      </div>
    </main>
  );
}
