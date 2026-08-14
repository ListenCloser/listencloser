"use client";

import { useEffect, useRef, useState } from "react";
import { useTransport, type CompareSide, type PlaybackSource } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

type PlaybackDomain = "performance" | "notation";

function sourceDomain(source: PlaybackSource | null): PlaybackDomain | null {
  if (!source) return null;
  if (source.role === "score") return "notation";
  return "performance";
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function SourceMenu({
  triggerLabel,
  triggerAria,
  options,
  selectedId,
  onSelect,
}: {
  triggerLabel: string;
  triggerAria: string;
  options: { id: string; label: string }[];
  selectedId: string | null;
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

  return (
    <div className="piece-source-select" ref={ref}>
      <button
        type="button"
        className="piece-source-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={triggerAria}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span>{triggerLabel}</span>
        <span className="piece-caret" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="piece-source-menu" role="listbox" aria-label={triggerAria}>
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              role="option"
              aria-selected={selectedId === option.id}
              onClick={() => {
                onSelect(option.id);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TransportBar() {
  const {
    transport,
    seek,
    setActiveSource,
    setLoop,
    stop,
    toggle,
    toggleLoop,
    startCompare,
    setCompareSide,
    setCompareSource,
    exitCompare,
  } = useTransport();
  const {
    isPlaying,
    position,
    duration,
    loopEnabled,
    loopStart,
    loopEnd,
    activeSource,
    sources,
    compareEnabled,
    compareA,
    compareB,
    activeSide,
  } = transport;
  const { workspace, toggleInspector } = useWorkspace();
  const hasSource = Boolean(activeSource);
  const hasInsights = workspace.insights.length > 0;

  const selection = workspace.selection;
  const selectionTimeRange = selection?.timeRange ?? null;
  const selectionDomain = selectionTimeRange?.domain ?? null;
  const activeDomain = sourceDomain(activeSource);
  const domainMatches = selectionDomain !== null && activeDomain !== null && selectionDomain === activeDomain;

  const loopSelectionActive =
    loopEnabled &&
    loopStart !== null &&
    loopEnd !== null &&
    selectionTimeRange !== null &&
    Math.abs(loopStart - selectionTimeRange.start) < 0.05 &&
    Math.abs(loopEnd - selectionTimeRange.end) < 0.05;

  const applyLoopSelection = () => {
    if (!selectionTimeRange || !hasSource) return;
    if (!domainMatches) {
      // Cross-domain loop would silently treat notation seconds as performance
      // seconds (or vice versa). Disable to avoid misleading loops.
      return;
    }
    setLoop(selectionTimeRange.start, selectionTimeRange.end);
    if (!loopEnabled) toggleLoop();
  };

  const original = sources.find((item) => item.role === "original") ?? sources[0] ?? null;
  const defaultB = sources.find((item) => item.id !== original?.id && ["transcription", "score"].includes(item.role))
    ?? sources.find((item) => item.id !== original?.id)
    ?? null;

  const joinCompare = () => {
    if (!original || !defaultB || original.id === defaultB.id) return;
    startCompare(original, defaultB);
  };

  return (
    <section className="piece-transport" aria-label="Playback">
      <div className="piece-transport-controls">
        <button
          type="button"
          className="piece-play"
          onClick={toggle}
          aria-label={hasSource ? (isPlaying ? "Pause" : "Play") : "Import audio to enable playback"}
          disabled={!hasSource}
        >
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button type="button" className="piece-stop" onClick={stop} aria-label="Stop" disabled={!hasSource}>
          ■
        </button>
      </div>

      <div className="piece-timeline">
        <div className="piece-time">
          <span>{formatTime(position)}</span>
          <span>{formatTime(duration)}</span>
        </div>
        <input
          className="piece-seek"
          type="range"
          aria-label="Playback position"
          min={0}
          max={Math.max(duration, 0.01)}
          step={0.01}
          value={Math.min(position, Math.max(duration, 0.01))}
          onChange={(event) => seek(Number(event.target.value))}
          disabled={!hasSource || duration <= 0}
        />
      </div>

      <div className="piece-transport-controls">
        <button
          className={`piece-stop ${loopEnabled ? "piece-control-active" : ""}`}
          onClick={() => {
            if (!loopEnabled && (loopStart === null || loopEnd === null) && duration > 0) setLoop(0, duration);
            toggleLoop();
          }}
          aria-label="Toggle loop"
          disabled={!hasSource}
        >
          ↺
        </button>
        {selectionTimeRange && (
          <button
            className={`piece-stop ${loopSelectionActive ? "piece-control-active" : ""}${!domainMatches ? " piece-control-disabled" : ""}`}
            onClick={applyLoopSelection}
            aria-label={domainMatches ? "Loop selection" : "Loop selection (disabled: selection and source have different time domains)"}
            aria-pressed={loopSelectionActive}
            disabled={!hasSource || !domainMatches}
            title={
              domainMatches
                ? `Loop the selected region (${selectionTimeRange.start.toFixed(1)}s – ${selectionTimeRange.end.toFixed(1)}s)`
                : `Selection is in ${selectionDomain} time; active source is ${activeDomain} time. Loop disabled.`
            }
          >
            ↻
          </button>
        )}
      </div>

      {sources.length > 0 && (
        <div className="piece-hearing">
          {!compareEnabled ? (
            <>
              <SourceMenu
                triggerLabel={activeSource ? activeSource.label : "No source"}
                triggerAria={`Listening to: ${activeSource ? activeSource.label : "no source"}`}
                options={sources.map((item) => ({ id: item.id, label: item.label }))}
                selectedId={activeSource?.id ?? null}
                onSelect={(id) => {
                  const next = sources.find((item) => item.id === id);
                  if (next) setActiveSource(next);
                }}
              />
              {sources.length > 1 && (
                <button type="button" className="piece-compare-enter" onClick={joinCompare}>
                  Compare
                </button>
              )}
              {activeSource?.role === "score" && (
                <span
                  className="piece-hearing-note"
                  style={{ fontSize: "var(--fs-xs)", color: "var(--muted)", whiteSpace: "nowrap" }}
                  title="Original and Transcription play in performance time; the Score rendition plays in notation time."
                >
                  notation time
                </span>
              )}
            </>
          ) : (
            <div className="piece-compare" role="group" aria-label="Compare playback">
              <span className="piece-hearing-label">Compare</span>
              {(["A", "B"] as const).map((side) => {
                const sideSource = side === "A" ? compareA : compareB;
                const other = side === "A" ? compareB : compareA;
                return (
                  <SourceMenu
                    key={side}
                    triggerLabel={`${side} · ${sideSource ? sideSource.label : "Choose…"}`}
                    triggerAria={`${side}: ${sideSource ? sideSource.label : "Choose…"}`}
                    options={sources
                      .filter((item) => item.id !== other?.id)
                      .map((item) => ({ id: item.id, label: item.label }))}
                    selectedId={sideSource?.id ?? null}
                    onSelect={(id) => {
                      const next = sources.find((item) => item.id === id);
                      if (next) setCompareSource(side, next);
                    }}
                  />
                );
              })}
              <div className="piece-compare-sides" role="group" aria-label="Active compare side">
                {(["A", "B"] as const).map((side) => (
                  <button
                    key={side}
                    type="button"
                    className={`piece-compare-chip${activeSide === side ? " active" : ""}`}
                    aria-pressed={activeSide === side}
                    onClick={() => setCompareSide(side)}
                  >
                    {side}
                  </button>
                ))}
              </div>
              <button type="button" className="piece-compare-exit" aria-label="Exit compare" onClick={exitCompare}>
                ✕
              </button>
            </div>
          )}
        </div>
      )}

      {hasInsights && (
        <button
          type="button"
          className={`piece-inspector-toggle ${workspace.inspectorCollapsed ? "" : "active"}`}
          aria-label={workspace.inspectorCollapsed ? "Show analysis" : "Hide analysis"}
          aria-pressed={!workspace.inspectorCollapsed}
          onClick={toggleInspector}
          title={workspace.inspectorCollapsed ? "Show analysis" : "Hide analysis"}
        >
          🔎
        </button>
      )}
    </section>
  );
}