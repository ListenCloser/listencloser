"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { availableRepresentations, representationById, type RepresentationId } from "@/lib/representations";
import { useWorkspace, type TranscriptionProfile } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";
import { presentableTitle } from "@/lib/format";

function TranscriptionModeToggle() {
  const { workspace, setTranscriptionProfile } = useWorkspace();
  const options: { id: TranscriptionProfile; label: string }[] = [
    { id: "auto", label: "Auto" },
    { id: "solo_piano", label: "Solo piano" },
  ];
  return (
    <div className="transcription-mode" role="group" aria-label="Transcription mode">
      <span className="transcription-mode-label">Transcription</span>
      <div className="transcription-mode-options">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            aria-pressed={workspace.transcriptionProfile === option.id}
            className={workspace.transcriptionProfile === option.id ? "active" : ""}
            onClick={() => setTranscriptionProfile(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
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
        className="repr-more-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        More <span aria-hidden="true">&#9662;</span>
      </button>
      {open && (
        <div className="repr-more-menu" role="listbox">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="option"
              aria-selected={activeId === item.id}
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

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport, setActiveRepresentation } = useWorkspace();
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);
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

  if (workspace.isLoadingWork) {
    return (
      <main className="piece-desk">
        <div className="piece-loading" role="status">
          <span className="spinner" aria-hidden="true" />
          <div className="piece-loading-copy">
            <strong>Opening your music</strong>
            <span>Loading the saved recording, transcription, and analysis.</span>
          </div>
        </div>
      </main>
    );
  }
  if (!available.length) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;

  const view = representationById(activeView ?? available[0].id);
  if (!view) return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;
  const ViewComponent = view.component;

  const primaryTabs = available.slice(0, PRIMARY_TAB_COUNT);
  const overflowTabs = available.slice(PRIMARY_TAB_COUNT);
  const activeInOverflow = overflowTabs.some((t) => t.id === activeView);

  return <main className="piece-desk">
    <header className="piece-desk-heading">
      <h1 title={activeWork?.title}>{presentableTitle(activeWork?.title ?? "Untitled piece")}</h1>
    </header>

    <nav className="piece-view-tabs" role="tablist" aria-label="Workspace views">
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
          items={overflowTabs.map((t) => ({ id: t.id, title: t.title }))}
          activeId={activeInOverflow ? activeView : null}
          onSelect={(id) => setActiveRepresentation(id as RepresentationId)}
        />
      )}
    </nav>

    <section className="piece-active-view" aria-label={view.title}>
      <ViewComponent />
    </section>
  </main>;
}

function EmptyDesk({ signedIn, canImport, onImport }: { signedIn: boolean; canImport: boolean; onImport: () => void }) {
  return (
    <main className="piece-desk piece-empty">
      <h1>Start with a recording.</h1>
      <p>Upload an audio file. We will keep the original, create a playable transcription, and give you a piano roll, score, and analysis to inspect together.</p>
      <div style={{ display: "grid", gap: "var(--s-3)", justifyContent: "center", justifyItems: "center" }}>
        <button className="btn btn-primary" onClick={onImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import"}</button>
        <TranscriptionModeToggle />
      </div>
      <small>WAV, MP3, M4A, FLAC, OGG, or AAC &middot; up to 4 MB</small>
    </main>
  );
}
