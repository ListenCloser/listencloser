"use client";

import { useEffect, useMemo } from "react";
import { availableRepresentations, representationById } from "@/lib/representations";
import { useWorkspace, type TranscriptionProfile } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";

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
  const { workspace, requestImport, setActiveRepresentation } = useWorkspace();
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

  if (workspace.isLoadingWork) return <WorkspaceLoadingSkeleton />;
  if (!available.length) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;

  const view = representationById(activeView ?? available[0].id);
  if (!view) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;
  const ViewComponent = view.component;

  return (
    <main className="piece-desk piece-desk-v3">
      <div className="representation-toolbar">
        <nav className="piece-view-tabs piece-view-tabs-v3" role="tablist" aria-label="Music representation">
          {available.map((def) => (
            <button
              key={def.id}
              type="button"
              role="tab"
              aria-selected={activeView === def.id}
              className={activeView === def.id ? "active" : ""}
              onClick={() => setActiveRepresentation(def.id)}
            >
              {def.title}
            </button>
          ))}
        </nav>
      </div>

      <section className="piece-active-view piece-active-view-v3" aria-label={view.title}>
        <ViewComponent />
      </section>
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
