"use client";

import { useEffect, useMemo } from "react";
import { availableRepresentations, representationById } from "@/lib/representations";
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

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport, setActiveRepresentation } = useWorkspace();
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);
  // Derive availability once per representations/insights change, not per render:
  // availableRepresentations returns a fresh array, and a fresh dependency array
  // in the effect below would re-run it on every render (infinite loop when the
  // workspace is empty and setActiveRepresentation(null) produces new state).
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
            <strong>Opening your music…</strong>
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

  return <main className="piece-desk">
    <header className="piece-desk-heading">
      <div className="piece-desk-title">
        <h1 title={activeWork?.title}>{presentableTitle(activeWork?.title ?? "Untitled piece")}</h1>
        <p>{view.description}</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-3)" }}>
        <TranscriptionModeToggle />
        <button type="button" className="btn" onClick={requestImport}>Import another</button>
      </div>
    </header>

    <div className="piece-view-tabs" role="tablist" aria-label="Workspace views">
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
    </div>

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
        <button className="btn btn-primary" onClick={onImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import…"}</button>
        <TranscriptionModeToggle />
      </div>
      <small>WAV, MP3, M4A, FLAC, OGG, or AAC · up to 4 MB</small>
    </main>
  );
}