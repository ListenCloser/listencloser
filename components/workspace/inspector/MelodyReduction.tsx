"use client";

import type { Insight } from "@/lib/domain.types";
import {
  projectMelodyReduction,
  type MelodyReductionProjection,
} from "@/lib/melody-reduction";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import styles from "./MelodyReduction.module.css";

const NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"] as const;

function pitchName(pitch: number): string {
  return `${NOTE_NAMES[((pitch % 12) + 12) % 12]}${Math.floor(pitch / 12) - 1}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

function stringField(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function playbackActionLabel(role: PlaybackSource["role"] | null): string {
  switch (role) {
    case "original": return "Hear original audio";
    case "transcription": return "Hear transcription playback";
    case "score": return "Hear score playback";
    case "derived": return "Hear derived playback";
    default: return "Hear current playback";
  }
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
  playbackRole,
  canHear,
  onFocus,
  onHear,
}: {
  insight: Insight;
  projection: Extract<MelodyReductionProjection, { status: "supported" }>;
  playbackRole: PlaybackSource["role"] | null;
  canHear: boolean;
  onFocus: () => void;
  onHear: () => void;
}) {
  const { engine, method, model } = provenanceLabels(insight);
  const pitches = projection.notes.map((note) => note.pitch);
  const minPitch = Math.min(...pitches);
  const maxPitch = Math.max(...pitches);
  const pitchSpan = Math.max(1, maxPitch - minPitch);
  const duration = Math.max(0.001, projection.endSeconds - projection.startSeconds);
  const x = (seconds: number) => 8 + ((seconds - projection.startSeconds) / duration) * 464;
  const y = (pitch: number) => 82 - ((pitch - minPitch) / pitchSpan) * 68;

  return (
    <section className={styles.reduction} aria-label="Experimental melody reduction">
      <div className={styles.header}>
        <strong>Melody reduction</strong>
        <span className={styles.qualifier}>Experimental · {engine}</span>
      </div>
      <p className={styles.copy}>
        A method-specific proposed melodic line mapped back to exact notes in this Piano Roll Version.
      </p>

      <div className={styles.object}>
        <svg
          viewBox="0 0 480 96"
          role="img"
          aria-label={`Proposed melody reduction with ${projection.notes.length} exact source notes`}
        >
          {projection.notes.map((note) => {
            const startX = x(note.startSeconds);
            const endX = x(note.endSeconds);
            return (
              <rect
                key={note.id}
                data-melody-note-id={note.id}
                x={startX}
                y={y(note.pitch)}
                width={Math.max(3, endX - startX)}
                height={7}
                rx={2}
                fill="var(--accent)"
              >
                <title>{pitchName(note.pitch)} · exact note {note.id}</title>
              </rect>
            );
          })}
        </svg>
      </div>

      <p className={styles.note}>
        {projection.notes.length} proposed notes · source Version {projection.sourceVersionId.slice(0, 8)}. This is not a verified melody label or a top-voice rule.
      </p>

      <div className={styles.actions}>
        <button type="button" onClick={onFocus}>Focus in Piano Roll</button>
        <button type="button" onClick={onHear} disabled={!canHear}>
          {playbackActionLabel(playbackRole)}
        </button>
      </div>
      <p className={styles.note}>
        Hear uses the current playback source; it does not synthesize or silently switch to an isolated melody track.
      </p>

      <details className={styles.details}>
        <summary>Inspect provenance</summary>
        <dl>
          <dt>Source Version</dt><dd>{projection.sourceVersionId}</dd>
          <dt>Engine</dt><dd>{engine}</dd>
          <dt>Method</dt><dd>{method}</dd>
          {model && <><dt>Model</dt><dd>{model}</dd></>}
          <dt>Identity mapping</dt><dd>{projection.notes.length}/{projection.notes.length} persisted Piano Roll note entities</dd>
          <dt>Qualification</dt><dd>Experimental. LStoM evidence is established for arranged pop MIDI; general piano and dense polyphony remain ambiguous.</dd>
        </dl>
      </details>
    </section>
  );
}

export default function MelodyReduction({ insight }: { insight: Insight }) {
  const { workspace, setSelection, setActiveRepresentation } = useWorkspace();
  const { transport, seek, play } = useTransport();
  const pianoRoll = workspace.representations.find((item) => item.kind === "piano_roll");
  if (!pianoRoll) return null;

  const projection = projectMelodyReduction(insight, pianoRoll);
  if (projection.status !== "supported") return null;

  return (
    <MelodyReductionObject
      insight={insight}
      projection={projection}
      playbackRole={transport.activeSource?.role ?? null}
      canHear={Boolean(transport.activeSource)}
      onFocus={() => {
        setSelection({
          timeRange: {
            start: projection.startSeconds,
            end: projection.endSeconds,
            domain: "performance",
          },
          noteIds: projection.notes.map((note) => note.id),
          provenance: { origin: null, timeExact: true, measureApproximate: false },
        });
        setActiveRepresentation("piano_roll");
      }}
      onHear={() => {
        seek(projection.startSeconds);
        play();
      }}
    />
  );
}
