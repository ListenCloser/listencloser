"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import TabStrip, { type TabIntentSource } from "@/components/ui/TabStrip";
import {
  REPRESENTATIONS,
  availableRepresentations,
  type RepresentationId,
} from "./representations/registry";
import { preloadScoreRenderer } from "@/lib/score-renderer";
import { useWorkspace } from "@/lib/stores/workspace";
import { deriveAvailability } from "@/lib/representation-availability";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";
import styles from "./RepresentationStack.module.css";

const ORIENTATION_CUE_MS = 560;
const SCORE_POINTER_INTENT_MS = 120;

function WorkspaceLoadingSkeleton() {
  return (
    <main className={styles.root} aria-busy="true" aria-label="Opening recording">
      <div className={styles.toolbar}>
        <TabStrip
          label="Music representation"
          items={REPRESENTATIONS.map((definition) => ({
            id: definition.id,
            label: definition.title,
            disabled: true,
          }))}
          value={null}
          onChange={() => undefined}
        />
        <span className={styles.opening} aria-hidden="true">Opening…</span>
      </div>
      <div className={styles.loadingCanvas} role="status">
        <div className={styles.loadingVisual} aria-hidden="true">
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
  const activeSymbolicSourceLabel = activeView === "piano_roll"
    ? workspace.representations.find((item) => item.kind === "piano_roll")?.sourceLabel
    : activeView === "score"
      ? workspace.representations.find((item) => item.kind === "score")?.sourceLabel
      : null;

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
    if (signedIn && workspace.activeWorkId) return <WorkspaceLoadingSkeleton />;
    return <EmptyDesk signedIn={signedIn} canImport={canImport} onImport={requestImport} />;
  }

  const renderedViews = available.filter((definition) => definition.id === activeView || mountedViews.has(definition.id));

  return (
    <main className={styles.root}>
      <div className={styles.toolbar}>
        <TabStrip
          label="Music representation"
          items={REPRESENTATIONS.map((definition) => {
            const isAvailable = availableIds.has(definition.id);
            return {
              id: definition.id,
              label: isAvailable
                ? definition.title
                : `${definition.title} · ${workspace.analysisState === "analyzing" ? "Preparing" : "Unavailable"}`,
              disabled: !isAvailable,
            };
          })}
          value={activeView}
          onChange={(nextView) => {
            cancelScoreIntentWarmup();
            setActiveRepresentation(nextView);
          }}
          onIntentStart={handleRepresentationIntentStart}
          onIntentEnd={handleRepresentationIntentEnd}
        />
        {activeSymbolicSourceLabel && (
          <span className={styles.sourceNote} role="note" aria-label="Symbolic representation source">
            {activeSymbolicSourceLabel}
          </span>
        )}
      </div>

      {renderedViews.map((definition) => {
        const ViewComponent = definition.component;
        const active = definition.id === activeView;
        return (
          <section
            key={definition.id}
            className={styles.view}
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
    <main className={`${styles.root} ${styles.emptyRoot}`}>
      <div className={styles.emptyCopy}>
        <h1>Import a recording</h1>
        <p>Open audio to explore synchronized representations and analysis.</p>
        <Button variant="primary" onClick={onImport} disabled={!signedIn || !canImport}>
          Import audio
        </Button>
        <span className={styles.formats}>WAV · MP3 · M4A · FLAC · OGG · AAC</span>
      </div>
    </main>
  );
}
