"use client";

import { Disclosure, DisclosureButton, DisclosurePanel } from "@headlessui/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import type { Insight } from "@/lib/domain.types";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import {
  findMelodyAuditionJob,
  findMelodyPlaybackSource,
  startMelodyAuditionWorkflow,
  type MelodyPlaybackSourceRef,
} from "@/lib/melody-playback-client";
import {
  projectMelodyReduction,
  type MelodyReductionProjection,
} from "@/lib/melody-reduction";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import styles from "./MelodyReduction.module.css";

const NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"] as const;
const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

type SupportedMelodyReduction = Extract<MelodyReductionProjection, { status: "supported" }>;
type MelodyReductionNote = SupportedMelodyReduction["notes"][number];
type AuditionState = "idle" | "preparing" | "disconnected" | "error";

function pitchName(pitch: number): string {
  return `${NOTE_NAMES[((pitch % 12) + 12) % 12]}${Math.floor(pitch / 12) - 1}`;
}

function formatClock(seconds: number): string {
  const value = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(value / 60);
  const remainder = value % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

function stringField(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function provenanceLabels(insight: Insight): { engine: string; method: string; model: string | null } {
  const provenance = asRecord(insight.provenance);
  const engine = asRecord(provenance?.engine);
  const evidence = asRecord(insight.evidence);
  return {
    engine: stringField(engine, "engine") ?? stringField(engine, "name") ?? "LStoM",
    method: stringField(provenance, "method") ?? stringField(evidence, "heuristic") ?? "method-specific melody interpretation",
    model: stringField(evidence, "model_version") ?? stringField(engine, "model_version"),
  };
}

export function MelodyReductionObject({
  insight,
  projection,
  pieceEndSeconds,
  playheadSeconds,
  selectedNoteId,
  auditionState = "idle",
  auditionError = null,
  onPlayMelody,
  onSelectNote,
}: {
  insight: Insight;
  projection: SupportedMelodyReduction;
  pieceEndSeconds: number;
  playheadSeconds?: number | null;
  selectedNoteId?: string | null;
  auditionState?: AuditionState;
  auditionError?: string | null;
  onPlayMelody: () => void;
  onSelectNote: (note: MelodyReductionNote) => void;
}) {
  const { engine, method, model } = provenanceLabels(insight);
  const pitches = projection.notes.map((note) => note.pitch);
  const minPitch = Math.min(...pitches);
  const maxPitch = Math.max(...pitches);
  const pitchSpan = Math.max(1, maxPitch - minPitch);
  const timelineEnd = Math.max(pieceEndSeconds, projection.endSeconds, 0.001);
  const x = (seconds: number) => 10 + (Math.max(0, seconds) / timelineEnd) * 460;
  const y = (pitch: number) => 58 - ((pitch - minPitch) / pitchSpan) * 42;
  const activePlayhead = typeof playheadSeconds === "number"
    && playheadSeconds >= 0
    && playheadSeconds <= timelineEnd
    ? playheadSeconds
    : null;
  const preparing = auditionState === "preparing";

  return (
    <section className={styles.reduction} aria-label="Experimental melody reduction">
      <div className={styles.header}>
        <div className={styles.heading}>
          <strong>Melody</strong>
          <span className={styles.count}>{projection.notes.length} notes</span>
        </div>
        <span className={styles.qualifier}>Experimental</span>
      </div>

      <div className={styles.object}>
        <svg
          viewBox="0 0 480 88"
          role="group"
          aria-label={`Proposed melody reduction across the full Piano Roll timeline with ${projection.notes.length} exact source notes`}
        >
          <line
            x1={10}
            x2={470}
            y1={75}
            y2={75}
            stroke="var(--border)"
            strokeWidth={0.7}
            strokeOpacity={0.5}
          />
          <text x={10} y={84} className={styles.timeLabel}>0:00</text>
          <text x={470} y={84} textAnchor="end" className={styles.timeLabel}>
            {formatClock(timelineEnd)}
          </text>
          {activePlayhead !== null && (
            <line
              className={styles.playhead}
              data-melody-playhead="true"
              x1={x(activePlayhead)}
              x2={x(activePlayhead)}
              y1={8}
              y2={75}
            />
          )}
          {projection.notes.map((note) => {
            const startX = x(note.startSeconds);
            const endX = x(note.endSeconds);
            const selected = selectedNoteId === note.id;
            const playing = activePlayhead !== null
              && activePlayhead >= note.startSeconds
              && activePlayhead <= note.endSeconds;
            const label = `${pitchName(note.pitch)} at ${formatClock(note.startSeconds)}`;
            return (
              <rect
                key={note.id}
                className={styles.melodyNote}
                data-melody-note-id={note.id}
                data-selected={selected ? "true" : undefined}
                data-playing={playing ? "true" : undefined}
                x={startX}
                y={y(note.pitch)}
                width={Math.max(4, endX - startX)}
                height={7}
                rx={2}
                role="button"
                tabIndex={0}
                aria-label={`Show ${label} in Piano Roll`}
                aria-pressed={selected}
                onClick={() => onSelectNote(note)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  onSelectNote(note);
                }}
              >
                <title>{label}</title>
              </rect>
            );
          })}
        </svg>
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          className={styles.playAction}
          onClick={onPlayMelody}
          disabled={preparing}
          aria-busy={preparing}
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5.25 3.75 12 8l-6.75 4.25z" fill="currentColor" />
          </svg>
          <span>{preparing ? "Preparing melody…" : "Play melody"}</span>
        </button>

        <Disclosure>
          {({ open }) => (
            <div className={styles.about}>
              <DisclosureButton className={styles.aboutButton}>
                <span>About</span>
                <svg
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                  className={open ? styles.chevronOpen : styles.chevron}
                >
                  <path d="m5 6 3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </DisclosureButton>
              <DisclosurePanel className={styles.detailsPanel}>
                <dl>
                  <dt>Source</dt><dd>Version {projection.sourceVersionId}</dd>
                  <dt>Engine</dt><dd>{engine}</dd>
                  <dt>Method</dt><dd>{method}</dd>
                  {model && <><dt>Model</dt><dd>{model}</dd></>}
                  <dt>Mapping</dt><dd>{projection.notes.length}/{projection.notes.length} exact Piano Roll notes</dd>
                  <dt>Playback</dt><dd>Synthesized from these proposed notes, not isolated from the recording.</dd>
                  <dt>Limit</dt><dd>Experimental interpretation, not a verified melody label or top-voice rule. LStoM is established on arranged pop MIDI; general piano and dense polyphony remain ambiguous.</dd>
                </dl>
              </DisclosurePanel>
            </div>
          )}
        </Disclosure>
      </div>
      {auditionError && <p className={styles.auditionError} role="alert">{auditionError}</p>}
    </section>
  );
}

export default function MelodyReduction({ insight }: { insight: Insight }) {
  const { workspace, setSelection, setActiveRepresentation } = useWorkspace();
  const { transport, seek, play, setActiveSource, audioRef } = useTransport();
  const [melodySource, setMelodySource] = useState<MelodyPlaybackSourceRef | null>(null);
  const [auditionState, setAuditionState] = useState<AuditionState>("idle");
  const [auditionError, setAuditionError] = useState<string | null>(null);
  const actionInFlightRef = useRef(false);
  const pianoRoll = workspace.representations.find((item) => item.kind === "piano_roll");
  const activeWorkId = workspace.activeWorkId;
  const projection = useMemo(
    () => pianoRoll ? projectMelodyReduction(insight, pianoRoll) : null,
    [insight, pianoRoll],
  );

  const resolveDurableSource = useCallback(async (fresh = false) => {
    if (!activeWorkId || !projection || projection.status !== "supported") return null;
    if (fresh) clearWorkDataCache();
    const bundle = await getWorkBundle(activeWorkId);
    return {
      bundle,
      source: findMelodyPlaybackSource(bundle, projection.sourceVersionId, insight.id),
      job: findMelodyAuditionJob(bundle, projection.sourceVersionId, insight.id),
    };
  }, [activeWorkId, insight.id, projection]);

  useEffect(() => {
    setMelodySource(null);
    setAuditionState("idle");
    setAuditionError(null);
    actionInFlightRef.current = false;
    if (!activeWorkId || !projection || projection.status !== "supported") return;

    const controller = new AbortController();
    let disposed = false;
    void (async () => {
      try {
        const resolved = await resolveDurableSource();
        if (disposed || !resolved) return;
        if (resolved.source) {
          setMelodySource(resolved.source);
          return;
        }
        if (!resolved.job || !ACTIVE_JOB_STAGES.has(resolved.job.lifecycle.current)) return;

        setAuditionState("preparing");
        await waitForJob(resolved.job.id, () => undefined, { signal: controller.signal });
        if (disposed) return;
        const completed = await resolveDurableSource(true);
        if (disposed || !completed?.source) {
          throw new Error("Melody playback finished without a playable source");
        }
        setMelodySource(completed.source);
        setAuditionState("idle");
      } catch (cause) {
        if (disposed || (cause instanceof DOMException && cause.name === "AbortError")) return;
        if (cause instanceof JobObservationError) {
          setAuditionState("disconnected");
          setAuditionError("Melody is still processing; this browser lost contact with the worker.");
        } else {
          setAuditionState("error");
          setAuditionError(cause instanceof Error ? cause.message : "Could not prepare melody playback");
        }
      }
    })();

    return () => {
      disposed = true;
      controller.abort();
    };
  }, [activeWorkId, projection, resolveDurableSource]);

  if (!pianoRoll || !projection || projection.status !== "supported") return null;

  const pieceEndSeconds = Math.max(
    projection.endSeconds,
    ...(pianoRoll.notes ?? []).map((note) => note.end),
  );
  const selectedNoteId = workspace.selection?.noteIds?.length === 1
    ? workspace.selection.noteIds[0]
    : null;

  const selectSingleNote = (note: MelodyReductionNote) => {
    setSelection({
      noteIds: [note.id],
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    setActiveRepresentation("piano_roll");
    if (transport.activeSource?.role !== "score") {
      seek(note.startSeconds);
    }
  };

  const startPlayback = (sourceRef: MelodyPlaybackSourceRef) => {
    const source: PlaybackSource = {
      id: sourceRef.id,
      label: "Melody",
      url: sourceRef.url,
      kind: "audio",
      role: "derived",
    };
    const currentPosition = transport.position;
    const targetPosition = transport.activeSource?.role === "score"
      || currentPosition < projection.startSeconds
      || currentPosition > projection.endSeconds
      ? projection.startSeconds
      : currentPosition;

    if (transport.activeSource?.id === source.id) {
      if (Math.abs(currentPosition - targetPosition) > 0.001) seek(targetPosition);
      play();
      return;
    }

    const audio = audioRef.current;
    setActiveSource(source);
    if (!audio) return;
    audio.addEventListener("loadedmetadata", () => {
      seek(targetPosition);
      play();
    }, { once: true });
  };

  const playMelody = async () => {
    if (!activeWorkId || actionInFlightRef.current) return;
    if (melodySource) {
      startPlayback(melodySource);
      return;
    }

    actionInFlightRef.current = true;
    setAuditionState("preparing");
    setAuditionError(null);
    try {
      let resolved = await resolveDurableSource(true);
      if (!resolved) throw new Error("Melody playback is unavailable for this Work");
      let source = resolved.source;
      if (!source) {
        let jobId: string;
        if (resolved.job && ACTIVE_JOB_STAGES.has(resolved.job.lifecycle.current)) {
          jobId = resolved.job.id;
        } else {
          jobId = await startMelodyAuditionWorkflow(
            projection.sourceVersionId,
            resolved.bundle.work.project_id,
            insight.id,
          );
        }
        await waitForJob(jobId, () => undefined);
        resolved = await resolveDurableSource(true);
        source = resolved?.source ?? null;
      }
      if (!source) throw new Error("Melody playback finished without a playable source");
      setMelodySource(source);
      setAuditionState("idle");
      startPlayback(source);
    } catch (cause) {
      if (cause instanceof JobObservationError) {
        setAuditionState("disconnected");
        setAuditionError("Melody is still processing; this browser lost contact with the worker.");
      } else {
        setAuditionState("error");
        setAuditionError(cause instanceof Error ? cause.message : "Could not prepare melody playback");
      }
    } finally {
      actionInFlightRef.current = false;
    }
  };

  return (
    <MelodyReductionObject
      insight={insight}
      projection={projection}
      pieceEndSeconds={pieceEndSeconds}
      playheadSeconds={transport.activeSource?.role === "score" ? null : transport.position}
      selectedNoteId={selectedNoteId}
      auditionState={auditionState}
      auditionError={auditionError}
      onPlayMelody={() => void playMelody()}
      onSelectNote={selectSingleNote}
    />
  );
}
