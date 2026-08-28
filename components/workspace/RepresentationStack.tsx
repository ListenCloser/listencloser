"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { availableRepresentations, representationById, type RepresentationId } from "@/lib/representations";
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

const PRIMARY_TAB_COUNT = 3;

function MoreMenu({
  items,
  activeId,
  onSelect,
}: {
  items: { id: string; title: string }[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div className="repr-more-select" ref={ref}>
      <button
        type="button"
        className={`repr-more-trigger${activeId ? " active" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        More
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
          <path d="m3 4.5 3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="repr-more-menu" role="menu">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitemradio"
              aria-checked={activeId === item.id}
              onClick={() => {
                onSelect(item.id);
                setOpen(false);
              }}
            >
              {item.title}
            </button>
          ))}
        </div>
      )}
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
      </div>
      <div className="piece-loading-canvas" role="status">
        <div className="piece-loading-header">
          <span className="loading-line loading-line-title" />
          <span className="loading-line loading-line-meta" />
        </div>
        <div className="piece-loading-visual" aria-hidden="true">
          {Array.from({ length: 7 }).map((_, row) => (
            <span key={row} style={{ "--loading-row": row } as React.CSSProperties} />
          ))}
        </div>
        <span className="sr-only">Opening the saved recording and its analysis.</span>
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

  const primaryTabs = available.slice(0, PRIMARY_TAB_COUNT);
  const overflowTabs = available.slice(PRIMARY_TAB_COUNT);
  const activeInOverflow = overflowTabs.some((tab) => tab.id === activeView);

  return (
    <main className="piece-desk piece-desk-v3">
      <div className="representation-toolbar">
        <nav className="piece-view-tabs piece-view-tabs-v3" role="tablist" aria-label="Music representation">
          {primaryTabs.map((def) => (
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
          {overflowTabs.length > 0 && (
            <MoreMenu
              items={overflowTabs.map((tab) => ({ id: tab.id, title: tab.title }))}
              activeId={activeInOverflow ? activeView : null}
              onSelect={(id) => setActiveRepresentation(id as RepresentationId)}
            />
          )}
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
        <span className="piece-eyebrow">New workspace</span>
        <h1>Bring in a recording.</h1>
        <p>Listen, transcribe, inspect notation, and understand the music without leaving the same workspace.</p>
        <button className="btn btn-primary empty-import-primary" onClick={onImport} disabled={!signedIn || !canImport}>
          {canImport ? "Import audio" : "Preparing import"}
        </button>
        <details className="transcription-settings">
          <summary>Transcription settings</summary>
          <TranscriptionModeToggle />
        </details>
        <small>WAV, MP3, M4A, FLAC, OGG, AAC · up to 4 MB</small>
      </div>
    </main>
  );
}
