"use client";

import { useState, useMemo } from "react";
import type { Entity, NoteEntity } from "@/lib/domain.types";
import DualPianoRoll from "./DualPianoRoll";
import DiffLane from "./DiffLane";

type Note = { pitch: number; start: number; end: number; velocity: number };

type DiffNote = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
  status: "unchanged" | "added" | "removed" | "modified";
  counterpart?: { pitch: number; start: number; end: number; velocity: number };
};

type ComparePanelProps = {
  versionA: { id: string; label: string; entities: Entity[] } | null;
  versionB: { id: string; label: string; entities: Entity[] } | null;
  onSelectVersionA: () => void;
  onSelectVersionB: () => void;
  diffNotes: DiffNote[] | null;
  onCompare?: (versionIdA: string, versionIdB: string) => void;
};

function extractNotes(entities: Entity[]): Note[] {
  return entities
    .filter((e) => e.kind === "note" && e.note)
    .map((e) => ({
      pitch: e.note!.pitch,
      start: e.note!.start_seconds,
      end: e.note!.end_seconds,
      velocity: e.note!.velocity,
    }));
}

function computeDiff(a: Note[], b: Note[]): DiffNote[] {
  const EPSILON = 0.01;
  const bRemaining = [...b];

  const results: DiffNote[] = [];

  for (const noteA of a) {
    const matchIdx = bRemaining.findIndex(
      (nb) =>
        nb.pitch === noteA.pitch &&
        Math.abs(nb.start - noteA.start) < EPSILON &&
        Math.abs(nb.end - noteA.end) < EPSILON
    );

    if (matchIdx >= 0) {
      const noteB = bRemaining[matchIdx];
      bRemaining.splice(matchIdx, 1);

      if (Math.abs(noteB.velocity - noteA.velocity) > 1) {
        results.push({
          ...noteA,
          status: "modified",
          counterpart: { ...noteB },
        });
      } else {
        results.push({ ...noteA, status: "unchanged" });
      }
    } else {
      results.push({ ...noteA, status: "removed" });
    }
  }

  for (const noteB of bRemaining) {
    results.push({ ...noteB, status: "added" });
  }

  return results;
}

export default function ComparePanel({
  versionA,
  versionB,
  onSelectVersionA,
  onSelectVersionB,
  diffNotes: externalDiffNotes,
  onCompare,
}: ComparePanelProps) {
  const [playheadTime, setPlayheadTime] = useState(0);
  const [bpm] = useState(120);

  const notesA = useMemo(
    () => (versionA ? extractNotes(versionA.entities) : []),
    [versionA]
  );
  const notesB = useMemo(
    () => (versionB ? extractNotes(versionB.entities) : []),
    [versionB]
  );

  const computedDiff = useMemo(
    () => externalDiffNotes ?? computeDiff(notesA, notesB),
    [externalDiffNotes, notesA, notesB]
  );

  const diffStats = useMemo(() => {
    const added = computedDiff.filter((d) => d.status === "added").length;
    const removed = computedDiff.filter((d) => d.status === "removed").length;
    const modified = computedDiff.filter((d) => d.status === "modified").length;
    const unchanged = computedDiff.filter((d) => d.status === "unchanged").length;
    return { added, removed, modified, unchanged };
  }, [computedDiff]);

  const allNotes = [...notesA, ...notesB];
  const minPitch = allNotes.length
    ? Math.min(...allNotes.map((n) => n.pitch))
    : 21;
  const maxPitch = allNotes.length
    ? Math.max(...allNotes.map((n) => n.pitch))
    : 108;

  if (!versionA && !versionB) {
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
        <span style={{ fontSize: 32, lineHeight: 1 }}>⇆</span>
        <div>
          <div style={{ fontWeight: "var(--fw-medium)", color: "var(--text)", marginBottom: "var(--s-1)" }}>
            No versions selected
          </div>
          <div>Select two versions to compare</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        overflow: "hidden",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-md)",
        background: "var(--panel)",
        margin: "var(--s-2)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-3)",
          padding: "var(--s-2) var(--s-3)",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel-2)",
          minHeight: 42,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--s-2)",
            flex: 1,
          }}
        >
          <span
            style={{
              fontSize: "var(--fs-xs)",
              fontWeight: "var(--fw-semibold)",
              color: "var(--accent)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            A
          </span>
          <button
            className="btn"
            style={{
              fontSize: "var(--fs-sm)",
              padding: "4px 12px",
              minWidth: 160,
              justifyContent: "space-between",
            }}
            onClick={onSelectVersionA}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {versionA ? versionA.label : "Select version A..."}
            </span>
            <span style={{ color: "var(--muted)", marginLeft: "var(--s-2)" }}>▾</span>
          </button>
        </div>

        <span style={{ color: "var(--muted)", fontSize: "var(--fs-sm)" }}>vs</span>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--s-2)",
            flex: 1,
            justifyContent: "flex-end",
          }}
        >
          <span
            style={{
              fontSize: "var(--fs-xs)",
              fontWeight: "var(--fw-semibold)",
              color: "var(--accent-2)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            B
          </span>
          <button
            className="btn"
            style={{
              fontSize: "var(--fs-sm)",
              padding: "4px 12px",
              minWidth: 160,
              justifyContent: "space-between",
              textAlign: "left",
            }}
            onClick={onSelectVersionB}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {versionB ? versionB.label : "Select version B..."}
            </span>
            <span style={{ color: "var(--muted)", marginLeft: "var(--s-2)" }}>▾</span>
          </button>
        </div>
      </div>

      {versionA && versionB && onCompare && (
        <button
          className="btn btn-primary"
          onClick={() => onCompare(versionA.id, versionB.id)}
          style={{ padding: "4px 12px", fontSize: "var(--fs-xs)" }}
        >
          Compare
        </button>
      )}

      <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>
        <DualPianoRoll
          notesA={notesA}
          notesB={notesB}
          diffNotes={computedDiff}
          bpm={bpm}
          playheadTime={playheadTime}
        />

        <DiffLane
          diffNotes={computedDiff}
          minPitch={minPitch}
          maxPitch={maxPitch}
          bpm={bpm}
        />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-4)",
          padding: "var(--s-2) var(--s-3)",
          borderTop: "1px solid var(--border)",
          background: "var(--panel-2)",
          fontSize: "var(--fs-xs)",
          color: "var(--muted)",
        }}
      >
        <span>
          A: <strong style={{ color: "var(--text)" }}>{notesA.length}</strong> notes
        </span>
        <span>
          B: <strong style={{ color: "var(--text)" }}>{notesB.length}</strong> notes
        </span>

        <span style={{ width: 1, height: 14, background: "var(--border)", margin: "0 var(--s-1)" }} />

        <span style={{ color: "var(--success)", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block", flexShrink: 0 }} />
          +{diffStats.added}
        </span>
        <span style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--danger)", display: "inline-block", flexShrink: 0 }} />
          −{diffStats.removed}
        </span>
        <span style={{ color: "var(--accent-2)", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-2)", display: "inline-block", flexShrink: 0 }} />
          ~{diffStats.modified}
        </span>
        <span>
          ≡{diffStats.unchanged}
        </span>

        {(notesA.length > 0 || notesB.length > 0) && (
          <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)" }}>
            {(
              (diffStats.unchanged /
                Math.max(1, diffStats.added + diffStats.removed + diffStats.modified + diffStats.unchanged)) *
              100
            ).toFixed(0)}
            % unchanged
          </span>
        )}
      </div>
    </div>
  );
}
