"use client";

import { useEffect } from "react";
import ListboxMenu from "@/components/ui/ListboxMenu";
import Tooltip from "@/components/ui/Tooltip";
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
    const help = original && defaultB
      ? `Compare ${original.label} with ${defaultB.label}`
      : "A second playback source is required";
    return (
      <Tooltip content={help}>
        <button
          type="button"
          className="transport-compare-trigger"
          disabled={!original || !defaultB}
          aria-label={!original || !defaultB ? "Compare unavailable: a second playback source is required" : undefined}
          onClick={() => {
            if (original && defaultB && original.id !== defaultB.id) startCompare(original, defaultB);
          }}
        >
          Compare
        </button>
      </Tooltip>
    );
  }

  return (
    <div className="transport-compare-active" role="group" aria-label="Compare playback sources">
      {(["A", "B"] as const).map((side) => {
        const source = side === "A" ? compareA : compareB;
        const other = side === "A" ? compareB : compareA;
        return (
          <div key={side} className={`transport-compare-side${activeSide === side ? " active" : ""}`}>
            <Tooltip content={`Listen to compare side ${side}`}>
              <button
                type="button"
                className="transport-compare-side-label"
                aria-pressed={activeSide === side}
                onClick={() => setCompareSide(side)}
              >
                {side}
              </button>
            </Tooltip>
            <ListboxMenu
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
      <Tooltip content="Exit compare mode">
        <button type="button" className="transport-compare-exit" onClick={exitCompare} aria-label="Exit compare">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <path d="M2 2l8 8M10 2l-8 8" />
          </svg>
        </button>
      </Tooltip>
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
  const activeSourceLabel = activeSource?.label ?? "source";
  const playbackActionLabel = isPlaying ? `Pause ${activeSourceLabel}` : `Play ${activeSourceLabel}`;

  const selection = workspace.selection;
  const selectionTimeRange = selection?.timeRange ?? null;
  const selectionDomain = selectionTimeRange?.domain ?? null;
  const activeDomain = sourceDomain(activeSource);
  const domainMatches = selectionDomain !== null && activeDomain !== null && selectionDomain === activeDomain;

  // A passage loop is only meaningful while the visible shared selection is
  // its scope. If the selection changes while looping, follow it. If the
  // selection disappears or becomes incompatible with the active source,
  // disable the loop rather than leaving invisible stale loop bounds behind.
  useEffect(() => {
    if (!loopEnabled) return;
    if (!selectionTimeRange || !domainMatches) {
      setLoop(null, null);
      toggleLoop();
      return;
    }
    const followsSelection =
      loopStart !== null &&
      loopEnd !== null &&
      Math.abs(loopStart - selectionTimeRange.start) < 0.05 &&
      Math.abs(loopEnd - selectionTimeRange.end) < 0.05;
    if (!followsSelection) {
      setLoop(selectionTimeRange.start, selectionTimeRange.end);
    }
  }, [domainMatches, loopEnabled, loopEnd, loopStart, selectionTimeRange, setLoop, toggleLoop]);

  const loopHelp = loopEnabled
    ? "Turn passage loop off"
    : !selectionTimeRange
      ? "Select a passage to loop"
      : !domainMatches
        ? "Selection uses a different time domain"
        : "Loop selected passage";

  if (!hasSource && sources.length === 0) {
    return <footer className="transport-bar transport-bar-v3 transport-bar-idle" aria-label="Playback" />;
  }

  return (
    <footer className="transport-bar transport-bar-v3" aria-label="Playback">
      <div className="transport-source-zone">
        <ListboxMenu
          triggerLabel={activeSource ? `Listening · ${activeSource.label}` : "Choose source"}
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
        <Tooltip content={playbackActionLabel}>
          <button
            type="button"
            className="transport-play-btn"
            onClick={toggle}
            aria-label={playbackActionLabel}
            disabled={!hasSource}
          >
            {isPlaying ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><rect x="1" y="1" width="4" height="12" rx="1" /><rect x="9" y="1" width="4" height="12" rx="1" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M2.5 1.5v11l10-5.5z" /></svg>
            )}
          </button>
        </Tooltip>
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
        <Tooltip content={loopHelp}>
          <button
            type="button"
            className={`transport-ctrl transport-ctrl-labeled${loopEnabled ? " active" : ""}`}
            onClick={() => {
              if (!selectionTimeRange || !domainMatches) return;
              if (loopEnabled) {
                toggleLoop();
                return;
              }
              setLoop(selectionTimeRange.start, selectionTimeRange.end);
              toggleLoop();
            }}
            aria-label="Toggle selected passage loop"
            aria-pressed={loopEnabled}
            disabled={!hasSource || !selectionTimeRange || !domainMatches}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M11 3h3v3" /><path d="M14 3l-3.25 3.25" /><path d="M5 13H2v-3" /><path d="M2 13l3.25-3.25" /><path d="M13.5 6A5.5 5.5 0 0 0 4 3.75" /><path d="M2.5 10A5.5 5.5 0 0 0 12 12.25" />
            </svg>
            <span className="transport-ctrl-text">Loop</span>
          </button>
        </Tooltip>
      </div>

      <div className="transport-compare-zone">
        <CompareTransportControl />
      </div>
    </footer>
  );
}
