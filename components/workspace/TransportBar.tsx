"use client";

import { useEffect } from "react";
import Button, { IconButton } from "@/components/ui/Button";
import { CloseIcon, LoopIcon, PauseIcon, PlayIcon } from "@/components/ui/Icons";
import ListboxMenu from "@/components/ui/ListboxMenu";
import Tooltip from "@/components/ui/Tooltip";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import styles from "./TransportBar.module.css";

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
        <Button
          variant="ghost"
          size="compact"
          disabled={!original || !defaultB}
          aria-label={!original || !defaultB ? "Compare unavailable: a second playback source is required" : undefined}
          onClick={() => {
            if (original && defaultB && original.id !== defaultB.id) startCompare(original, defaultB);
          }}
        >
          Compare
        </Button>
      </Tooltip>
    );
  }

  return (
    <div className={styles.compareActive} role="group" aria-label="Compare playback sources">
      {(["A", "B"] as const).map((side) => {
        const source = side === "A" ? compareA : compareB;
        const other = side === "A" ? compareB : compareA;
        const active = activeSide === side;
        return (
          <div
            key={side}
            className={`${styles.compareSide}${active ? ` ${styles.compareSideActive}` : ""}`}
          >
            <Tooltip content={`Listen to compare side ${side}`}>
              <Button
                variant="ghost"
                size="compact"
                aria-pressed={active}
                onClick={() => setCompareSide(side)}
              >
                {side}
              </Button>
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
        <IconButton compact variant="ghost" onClick={exitCompare} aria-label="Exit compare">
          <CloseIcon />
        </IconButton>
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
    return <footer className={`${styles.root} ${styles.idle}`} aria-label="Playback" />;
  }

  return (
    <footer className={styles.root} aria-label="Playback">
      <div className={styles.sourceZone}>
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

      <div className={styles.playbackZone}>
        <Tooltip content={playbackActionLabel}>
          <IconButton
            className={styles.playButton}
            variant="secondary"
            onClick={toggle}
            aria-label={playbackActionLabel}
            disabled={!hasSource}
          >
            {isPlaying ? <PauseIcon /> : <PlayIcon />}
          </IconButton>
        </Tooltip>
        <span className={styles.time}>{formatTime(position)}</span>
        <input
          className={styles.seek}
          type="range"
          aria-label="Playback position"
          min={0}
          max={Math.max(duration, 0.01)}
          step={0.01}
          value={Math.min(position, Math.max(duration, 0.01))}
          onChange={(event) => seek(Number(event.target.value))}
          disabled={!hasSource || duration <= 0}
        />
        <span className={`${styles.time} ${styles.timeMuted}`}>{formatTime(duration)}</span>
        <Tooltip content={loopHelp}>
          <Button
            variant="ghost"
            size="compact"
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
            <LoopIcon />
            <span>Loop</span>
          </Button>
        </Tooltip>
      </div>

      <div className={styles.compareZone}>
        <CompareTransportControl />
      </div>
    </footer>
  );
}
