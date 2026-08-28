"use client";

import { useEffect, useRef, useState } from "react";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
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
  compact = false,
}: {
  triggerLabel: string;
  triggerAria: string;
  options: { id: string; label: string }[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  compact?: boolean;
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
    <div className={`piece-source-select${compact ? " compact" : ""}`} ref={ref}>
      <button
        type="button"
        className="piece-source-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={triggerAria}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span>{triggerLabel}</span>
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
          <path d="m2.75 4 2.75 2.75L8.25 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
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

function CompareTransportControl() {
  const {
    transport,
    startCompare,
    setCompareSide,
    setCompareSource,
    exitCompare,
  } = useTransport();
  const { sources, compareEnabled, compareA, compareB, activeSide } = transport;

  if (sources.length <= 1) return null;

  const original = sources.find((item) => item.role === "original") ?? sources[0] ?? null;
  const defaultB = sources.find((item) => item.id !== original?.id && ["transcription", "score"].includes(item.role))
    ?? sources.find((item) => item.id !== original?.id)
    ?? null;

  if (!compareEnabled) {
    return (
      <button
        type="button"
        className="transport-compare-trigger"
        disabled={!original || !defaultB}
        onClick={() => {
          if (original && defaultB && original.id !== defaultB.id) startCompare(original, defaultB);
        }}
      >
        Compare
      </button>
    );
  }

  return (
    <div className="transport-compare-active" role="group" aria-label="Compare playback sources">
      {(["A", "B"] as const).map((side) => {
        const source = side === "A" ? compareA : compareB;
        const other = side === "A" ? compareB : compareA;
        return (
          <div key={side} className={`transport-compare-side${activeSide === side ? " active" : ""}`}>
            <button
              type="button"
              className="transport-compare-side-label"
              aria-pressed={activeSide === side}
              onClick={() => setCompareSide(side)}
            >
              {side}
            </button>
            <SourceMenu
              compact
              triggerLabel={source?.label ?? "Choose"}
              triggerAria={`${side} compare source`}
              options={sources
                .filter((item) => item.id !== other?.id)
                .map((item) => ({ id: item.id, label: item.label }))}
              selectedId={source?.id ?? null}
              onSelect={(id) => {
                const next = sources.find((item) => item.id === id);
                if (next) setCompareSource(side, next);
              }}
            />
          </div>
        );
      })}
      <button type="button" className="transport-compare-exit" onClick={exitCompare} aria-label="Exit compare">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
          <path d="M2 2l8 8M10 2l-8 8" />
        </svg>
      </button>
    </div>
  );
}

export default function TransportBar() {
  const {
    transport,
    seek,
    setActiveSource,
    setLoop,
    toggle,
    toggleLoop,
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
    if (!selectionTimeRange || !hasSource || !domainMatches) return;
    setLoop(selectionTimeRange.start, selectionTimeRange.end);
    if (!loopEnabled) toggleLoop();
  };

  if (!hasSource && sources.length === 0) {
    return <footer className="transport-bar transport-bar-v3 transport-bar-idle" aria-label="Playback" />;
  }

  return (
    <footer className="transport-bar transport-bar-v3" aria-label="Playback">
      <div className="transport-source-zone">
        <SourceMenu
          triggerLabel={activeSource ? activeSource.label : "Choose source"}
          triggerAria={`Playback source: ${activeSource ? activeSource.label : "none"}`}
          options={sources.map((item) => ({ id: item.id, label: item.label }))}
          selectedId={activeSource?.id ?? null}
          onSelect={(id) => {
            const next = sources.find((item) => item.id === id);
            if (next) setActiveSource(next);
          }}
        />
      </div>

      <div className="transport-playback-zone">
        <button
          type="button"
          className="transport-play-btn"
          onClick={toggle}
          aria-label={isPlaying ? "Pause" : "Play"}
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
        <button
          type="button"
          className={`transport-ctrl${loopEnabled ? " active" : ""}`}
          onClick={() => {
            if (!loopEnabled && (loopStart === null || loopEnd === null) && duration > 0) setLoop(0, duration);
            toggleLoop();
          }}
          aria-label="Toggle loop"
          title="Loop"
          disabled={!hasSource}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M11 3h3v3" /><path d="M14 3l-3.25 3.25" /><path d="M5 13H2v-3" /><path d="M2 13l3.25-3.25" /><path d="M13.5 6A5.5 5.5 0 0 0 4 3.75" /><path d="M2.5 10A5.5 5.5 0 0 0 12 12.25" />
          </svg>
        </button>
        {selectionTimeRange && (
          <button
            type="button"
            className={`transport-ctrl${loopSelectionActive ? " active" : ""}`}
            onClick={applyLoopSelection}
            aria-label="Loop selection"
            aria-pressed={loopSelectionActive}
            disabled={!hasSource || !domainMatches}
            title={domainMatches ? "Loop selected region" : "Selection uses a different time domain"}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
              <rect x="3" y="5" width="10" height="6" rx="1.5" strokeDasharray="2 2" />
            </svg>
          </button>
        )}
      </div>

      <div className="transport-compare-zone">
        <CompareTransportControl />
      </div>
    </footer>
  );
}
