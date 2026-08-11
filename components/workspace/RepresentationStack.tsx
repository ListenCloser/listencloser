"use client";

import { useEffect, useState } from "react";
import RepresentationLane from "./RepresentationLane";
import { useWorkspace } from "@/lib/stores/workspace";

const KIND_LABELS: Record<string, string> = {
  piano_roll: "Piano Roll",
  waveform: "Waveform",
  spectrogram: "Spectrogram",
  score: "Score",
  harmony: "Harmony",
  structure: "Structure",
  annotations: "Annotations",
};

export default function RepresentationStack({ signedIn = false, canImport = false }: { signedIn?: boolean; canImport?: boolean }) {
  const {
    workspace,
    expandRepresentation,
    requestImport,
  } = useWorkspace();

  const { representations } = workspace;
  const preferred = representations.some((item) => item.kind === "score") ? "score" : representations[0]?.kind;
  const [activeKind, setActiveKind] = useState<string | undefined>(preferred);

  useEffect(() => {
    if (!representations.some((item) => item.kind === activeKind)) setActiveKind(preferred);
  }, [activeKind, preferred, representations]);

  if (representations.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "var(--s-4)",
          flex: 1,
          padding: "var(--s-5)",
          color: "var(--muted)",
          fontSize: "var(--fs-sm)",
          textAlign: "center",
          border: "1px dashed var(--border)",
          borderRadius: "var(--r-md)",
          margin: "var(--s-2)",
        }}
      >
        <span className="empty-state-mark" aria-hidden="true">AI</span>
        <div>
          <div style={{ fontWeight: "var(--fw-medium)", color: "var(--text)", marginBottom: "var(--s-1)" }}>
            {signedIn ? "Start with an audio recording" : "Your music analysis workspace"}
          </div>
          <div>{signedIn ? "Transcribe it to a piano roll and score, then inspect musical structure." : "Sign in to import audio, generate notation, and explore evidence-backed analysis."}</div>
        </div>
        <button
          className="btn btn-primary"
          style={{ marginTop: "var(--s-2)" }}
          onClick={requestImport}
          disabled={!signedIn || !canImport}
        >
          {!signedIn ? "Sign in to begin" : canImport ? "Import audio" : "Processing service offline"}
        </button>
      </div>
    );
  }

  const active = representations.find((item) => item.kind === activeKind) ?? representations[0];

  return (
    <main className="piece-desk">
      <header className="piece-desk-heading">
        <div>
          <p className="piece-eyebrow">Active representation</p>
          <h1>{workspace.works.find((work) => work.id === workspace.activeWorkId)?.title ?? "Untitled work"}</h1>
          <p>Listen first, then move between the score and performance view.</p>
        </div>
        <button type="button" className="btn" onClick={requestImport}>Import another piece</button>
      </header>
      <div className="representation-switcher" role="tablist" aria-label="Musical representations">
        {representations.map((rep) => (
          <button key={rep.kind} type="button" role="tab" aria-selected={active?.kind === rep.kind} className={active?.kind === rep.kind ? "active" : ""} onClick={() => setActiveKind(rep.kind)}>
            {KIND_LABELS[rep.kind] ?? rep.label}
            <span>{rep.sourceLabel}</span>
          </button>
        ))}
      </div>
      {active && (
        <RepresentationLane
          kind={active.kind}
          label={KIND_LABELS[active.kind] ?? active.label}
          sourceLabel={active.sourceLabel}
          confidence={active.confidence}
          isExpanded
          onExpand={() => expandRepresentation(active.kind)}
          hideHeader
          workspaceNotes={active.notes?.length ? active.notes : undefined}
          musicxml={active.musicxml}
          audioUrl={active.audioUrl}
        />
      )}
    </main>
  );
}
