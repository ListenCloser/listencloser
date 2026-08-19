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
        <span className="piece-caret" aria-hidden="true">&#9662;</span>
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
  const { workspace } = useWorkspace();
  const hasSource = Boolean(activeSource);

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
    if (!domainMatches) return;
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
    <footer className="transport-bar" aria-label="Playback">
      <div className="transport-row-primary">
        <button
          type="button"
          className="transport-play-btn"
          onClick={toggle}
          aria-label={hasSource ? (isPlaying ? "Pause" : "Play") : "Import audio to enable playback"}
          disabled={!hasSource}
        >
          {isPlaying ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><rect x="1" y="1" width="4" height="12" rx="1" /><rect x="9" y="1" width="4" height="12" rx="1" /></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M2.5 1.5v11l10-5.5z" /></svg>
          )}
        </button>
        <span className="transport-time">{formatTime(position)}</span>
        <input
          className="transport-seek"
          type="range"
          aria-label="Playback position"
          min={0}
          max={Math.max(duration, 0.01)}
          step={0.01}
          value={Math.min(position, Math.max(duration, 0.01))}
          onChange={(event) => seek(Number(event.target.value))}
          disabled={!hasSource || duration <= 0}
        />
        <span className="transport-time transport-time-muted">{formatTime(duration)}</span>

        <span className="transport-divider" aria-hidden="true" />

        {sources.length > 0 && !compareEnabled && (
          <div className="transport-hearing">
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
              <button type="button" className="transport-compare-btn" onClick={joinCompare}>
                Compare
              </button>
            )}
          </div>
        )}

        {compareEnabled && (
          <div className="transport-compare" role="group" aria-label="Compare playback">
            {(["A", "B"] as const).map((side) => {
              const sideSource = side === "A" ? compareA : compareB;
              const other = side === "A" ? compareB : compareA;
              return (
                <SourceMenu
                  key={side}
                  triggerLabel={`${side} \u00b7 ${sideSource ? sideSource.label : "Choose\u2026"}`}
                  triggerAria={`${side}: ${sideSource ? sideSource.label : "Choose\u2026"}`}
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
            <div className="transport-compare-sides" role="group" aria-label="Active compare side">
              {(["A", "B"] as const).map((side) => (
                <button
                  key={side}
                  type="button"
                  className={`transport-compare-chip${activeSide === side ? " active" : ""}`}
                  aria-pressed={activeSide === side}
                  onClick={() => setCompareSide(side)}
                >
                  {side}
                </button>
              ))}
            </div>
            <button type="button" className="transport-compare-exit" aria-label="Exit compare" onClick={exitCompare}>
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true"><path d="M1 1l8 8M9 1l-8 8" /></svg>
            </button>
          </div>
        )}

        <span className="transport-divider" aria-hidden="true" />

        <div className="transport-controls-secondary">
          <button
            type="button"
            className={`transport-ctrl${loopEnabled ? " active" : ""}`}
            onClick={() => {
              if (!loopEnabled && (loopStart === null || loopEnd === null) && duration > 0) setLoop(0, duration);
              toggleLoop();
            }}
            aria-label="Toggle loop"
            disabled={!hasSource}
          >
            Loop
          </button>
          {selectionTimeRange && (
            <button
              type="button"
              className={`transport-ctrl${loopSelectionActive ? " active" : ""}${!domainMatches ? " disabled" : ""}`}
              onClick={applyLoopSelection}
              aria-label={domainMatches ? "Loop selection" : "Loop selection (disabled: selection and source have different time domains)"}
              aria-pressed={loopSelectionActive}
              disabled={!hasSource || !domainMatches}
              title={
                domainMatches
                  ? `Loop the selected region (${selectionTimeRange.start.toFixed(1)}s \u2013 ${selectionTimeRange.end.toFixed(1)}s)`
                  : `Selection is in ${selectionDomain} time; active source is ${activeDomain} time. Loop disabled.`
              }
            >
              Sel
            </button>
          )}
          <button type="button" className="transport-ctrl" onClick={stop} aria-label="Stop" disabled={!hasSource}>
            Stop
          </button>
        </div>
      </div>
    </footer>
  );
}
