"use client";

import { useEffect } from "react";
import { availableRepresentations, representationById } from "@/lib/representations";
import { useWorkspace } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";
import { presentableTitle } from "@/lib/format";

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const { workspace, requestImport, setActiveRepresentation } = useWorkspace();
  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId);
  const availability = deriveAvailability(workspace.representations, workspace.insights.length);
  const available = availableRepresentations(availability);
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
      <button type="button" className="btn" onClick={requestImport}>Import another</button>
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
      <button className="btn btn-primary" onClick={onImport} disabled={!signedIn || !canImport}>{canImport ? "Import audio" : "Preparing import…"}</button>
      <small>WAV, MP3, M4A, FLAC, OGG, or AAC · up to 4 MB</small>
    </main>
  );
}