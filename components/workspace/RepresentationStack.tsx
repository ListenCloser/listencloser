"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import TabStrip, { type TabIntentSource } from "@/components/ui/TabStrip";
import Tooltip from "@/components/ui/Tooltip";
import EmptyWorkspaceSignal from "@/components/workspace/EmptyWorkspaceSignal";
import {
  REPRESENTATIONS,
  availableRepresentations,
  type RepresentationId,
} from "./representations/registry";
import { preloadScoreRenderer } from "@/lib/score-renderer";
import { useWorkspace, type ScoreEngine, type TranscriptionProfile } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";

const ORIENTATION_CUE_MS = 560;
const SCORE_POINTER_INTENT_MS = 120;

function TranscriptionModeToggle() {
  const { workspace, setTranscriptionProfile } = useWorkspace();
  const options: { id: TranscriptionProfile; label: string; description: string }[] = [
    { id: "auto", label: "Auto", description: "Best default for most recordings" },
    { id: "solo_piano", label: "Solo piano", description: "Prefer piano-specific transcription" },
  ];
  return (
    <div className="transcription-mode" role="group" aria-label="Transcription mode">
      {options.map((option) => (
        <Tooltip key={option.id} content={option.description}>
          <button
            type="button"
            aria-pressed={workspace.transcriptionProfile === option.id}
            className={workspace.transcriptionProfile === option.id ? "active" : ""}
            onClick={() => setTranscriptionProfile(option.id)}
          >
            {option.label}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}

function ScoreEngineToggle() {
  const { workspace, setScoreEngine } = useWorkspace();
  const options: { id: ScoreEngine; label: string; description: string }[] = [
    { id: "musescore", label: "MuseScore", description: "Current notation baseline" },
    {
      id: "pm2s",
      label: "PM2S",
      description: "Experimental learned piano score reconstruction",
    },
  ];
  return (
    <div className="transcription-mode" role="group" aria-label="Score interpretation">
      {options.map((option) => (
        <Tooltip key={option.id} content={option.description}>
          <button
            type="button"
            aria-pressed={workspace.scoreEngine === option.id}
            className={workspace.scoreEngine === option.id ? "active" : ""}
            onClick={() => setScoreEngine(option.id)}
          >
            {option.label}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}

function WorkspaceLoadingSkeleton() {
  return (
    <main className="piece-desk piece-loading-shell" aria-busy="true" aria-label="Opening recording">
      <div className="representation-toolbar">
        <div className="piece-view-tabs piece-view-tabs-v3" aria-hidden="true">
          {REPRESENTATIONS.map((definition) => (
            <button key={definition.id} type="button" disabled tabIndex={-1}>
              {definition.title}
            </button>
          ))}
        </div>
        <span
          className="muted"
          style={{ alignSelf: "center", fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}
          aria-hidden="true"
        >
          Opening…
        </span>
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
  const { workspace, requestImport, setActiveRepresentation, clearSelection } = useWorkspace();
  const [mountedViews, setMountedViews] = useState<Set<RepresentationId>>(() => new Set());
  const [orientationCue, setOrientationCue] = useState(false);
  const orientationFrame = useRef<number | null>(null);
  const orientationTimeout = useRef<number | null>(null);
  const scoreIntentTimeout = useRef<number | null>(null);
  const availability = useMemo(
    () => deriveAvailability(workspace.representations, workspace.insights.length),
    [workspace.representations, workspace.insights.length],
  );
  const available = useMemo(() => availableRepresentations(availability), [availability]);
  const availableIds = useMemo(
    () => new Set(available.map((definition) => definition.id)),
    [available],
  );
  const activeView = available.some((view) => view.id === workspace.activeRepresentation)
    ? workspace.activeRepresentation
    : available[0]?.id ?? null;
  const preparingRepresentations =
    workspace.analysisState === "analyzing" && available.length < REPRESENTATIONS.length;

  function cancelScoreIntentWarmup() {
    if (scoreIntentTimeout.current === null) return;
    window.clearTimeout(scoreIntentTimeout.current);
    scoreIntentTimeout.current = null;
  }

  function handleRepresentationIntentStart(id: RepresentationId, source: TabIntentSource) {
    if (id !== "score" || activeView === "score" || !availableIds.has("score")) return;
    cancelScoreIntentWarmup();
    if (source === "focus") {
      preloadScoreRenderer();
      return;
    }
    scoreIntentTimeout.current = window.setTimeout(() => {
      scoreIntentTimeout.current = null;
      preloadScoreRenderer();
    }, SCORE_POINTER_INTENT_MS);
  }

  function handleRepresentationIntentEnd(id: RepresentationId, source: TabIntentSource) {
    if (id === "score" && source === "pointer") cancelScoreIntentWarmup();
  }

  useEffect(() => {
    // Initialize selection when a Work first exposes representations, but do
    // not erase an explicit user choice just because one progressive refresh
    // temporarily omits that representation. `activeView` may fall back for
    // the transient frame; the shared preference should return when evidence
    // becomes available again.
    if (workspace.activeRepresentation !== null) return;
    setActiveRepresentation(available[0]?.id ?? null);
  }, [available, setActiveRepresentation, workspace.activeRepresentation]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;

      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.matches("input, textarea, select") ||
          target.closest('[contenteditable]:not([contenteditable="false"])'))
      ) {
        return;
      }

      clearSelection();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection]);

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
      if (scoreIntentTimeout.current !== null) {
        window.clearTimeout(scoreIntentTimeout.current);
        scoreIntentTimeout.current = null;
      }
    };
  }, []);

  // Representation canvases are expensive client-side objects: OSMD builds a
  // full score SVG, WaveSurfer owns waveform state, and the spectrogram decodes
  // audio. Preserve views after their first visit within a work session so a
  // tab switch is a visibility change rather than a destroy/rebuild cycle.
  useEffect(() => {
    if (scoreIntentTimeout.current !== null) {
      window.clearTimeout(scoreIntentTimeout.current);
      scoreIntentTimeout.current = null;
    }
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

  if (workspace.isLoadingWork) return <WorkspaceLoadingSkeleton />;
  if (!available.length || !activeView) {
    // A durable selection whose representations are still hydrating is an
    // existing recording opening, not a first-run workspace. Keep the empty
    // import CTA reserved for a settled library with no active Work.
    if (signedIn && workspace.activeWorkId) return <WorkspaceLoadingSkeleton />;
    return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;
  }

  const renderedViews = available.filter((definition) => definition.id === activeView || mountedViews.has(definition.id));

  return (
    <main className="piece-desk piece-desk-v3">
      <div className="representation-toolbar" aria-busy={preparingRepresentations || undefined}>
        <TabStrip
          className="piece-view-tabs piece-view-tabs-v3"
          label="Music representation"
          items={REPRESENTATIONS.map((definition) => ({
            id: definition.id,
            label: definition.title,
            disabled: !availableIds.has(definition.id),
          }))}
          value={activeView}
          onChange={(nextView) => {
            cancelScoreIntentWarmup();
            setActiveRepresentation(nextView);
          }}
          onIntentStart={handleRepresentationIntentStart}
          onIntentEnd={handleRepresentationIntentEnd}
        />
        {preparingRepresentations && (
          <span
            className="muted"
            role="status"
            style={{ alignSelf: "center", fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}
          >
            Preparing representations…
          </span>
        )}
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
      <div className="empty-desk-art">
        <EmptyWorkspaceSignal />
      </div>
      <div className="empty-desk-copy">
        <h1>Import a recording</h1>
        <p>Move through waveform, notes, notation, and evidence without losing your place.</p>
        <button className="btn btn-primary empty-import-primary" onClick={onImport} disabled={!signedIn || !canImport}>
          Import audio
        </button>
        <details className="transcription-settings">
          <summary>Processing</summary>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Transcription</span>
          <TranscriptionModeToggle />
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Score interpretation</span>
          <ScoreEngineToggle />
        </details>
        <small>WAV, MP3, M4A, FLAC, OGG, AAC</small>
      </div>
    </main>
  );
}
