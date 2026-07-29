"use client";

import { useRef, useEffect } from "react";
import PianoRoll from "@/components/PianoRoll";

type Note = { pitch: number; start: number; end: number; velocity: number };

type DiffNote = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
  status: "unchanged" | "added" | "removed" | "modified";
  counterpart?: { pitch: number; start: number; end: number; velocity: number };
};

type DualPianoRollProps = {
  notesA: Note[];
  notesB: Note[];
  diffNotes: DiffNote[] | null;
  bpm?: number;
  playheadTime?: number;
};

export default function DualPianoRoll({
  notesA,
  notesB,
  diffNotes,
  bpm = 120,
  playheadTime = 0,
}: DualPianoRollProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scrollEls = container.querySelectorAll(".piano-roll-scroll");
    if (scrollEls.length < 2) return;

    const elA = scrollEls[0] as HTMLDivElement;
    const elB = scrollEls[1] as HTMLDivElement;

    const onScrollA = () => {
      if (syncing.current) return;
      syncing.current = true;
      elB.scrollLeft = elA.scrollLeft;
      syncing.current = false;
    };

    const onScrollB = () => {
      if (syncing.current) return;
      syncing.current = true;
      elA.scrollLeft = elB.scrollLeft;
      syncing.current = false;
    };

    elA.addEventListener("scroll", onScrollA, { passive: true });
    elB.addEventListener("scroll", onScrollB, { passive: true });

    return () => {
      elA.removeEventListener("scroll", onScrollA);
      elB.removeEventListener("scroll", onScrollB);
    };
  }, []);

  const statusMapA = new Map<string, "unchanged" | "added" | "removed" | "modified">();
  const statusMapB = new Map<string, "unchanged" | "added" | "removed" | "modified">();

  if (diffNotes) {
    for (const d of diffNotes) {
      const key = `${d.pitch}:${d.start.toFixed(4)}:${d.end.toFixed(4)}`;
      if (d.status === "removed") {
        statusMapA.set(key, "removed");
      } else if (d.status === "added") {
        statusMapB.set(key, "added");
      } else if (d.status === "modified") {
        statusMapA.set(key, "modified");
        if (d.counterpart) {
          const cKey = `${d.counterpart.pitch}:${d.counterpart.start.toFixed(4)}:${d.counterpart.end.toFixed(4)}`;
          statusMapB.set(cKey, "modified");
        }
      }
    }
  }

  const allNotes = [...notesA, ...notesB];
  const endTime = allNotes.reduce((t, n) => Math.max(t, n.end), 0);

  return (
    <div
      ref={containerRef}
      style={{
        display: "flex",
        flex: 1,
        overflow: "hidden",
        background: "var(--panel)",
      }}
    >
      <div
        style={{
          flex: 1,
          minWidth: 0,
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            fontSize: "var(--fs-xs)",
            fontWeight: "var(--fw-medium)",
            color: "var(--muted)",
            textAlign: "center",
            padding: "var(--s-1) 0",
            borderBottom: "1px solid var(--border)",
            background: "var(--panel-2)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Version A
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <PianoRoll notes={notesA} bpm={bpm} playheadTime={playheadTime} />
        </div>
      </div>

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            fontSize: "var(--fs-xs)",
            fontWeight: "var(--fw-medium)",
            color: "var(--muted)",
            textAlign: "center",
            padding: "var(--s-1) 0",
            borderBottom: "1px solid var(--border)",
            background: "var(--panel-2)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Version B
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <PianoRoll notes={notesB} bpm={bpm} playheadTime={playheadTime} />
        </div>
      </div>

      {diffNotes && diffNotes.length > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            display: "flex",
            gap: "var(--s-2)",
            padding: "var(--s-1) var(--s-3)",
            background: "var(--panel-2)",
            borderTop: "1px solid var(--border)",
            fontSize: "var(--fs-xs)",
            justifyContent: "center",
          }}
        >
          <span style={{ color: "var(--success)", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
            Added {diffNotes.filter((d) => d.status === "added").length}
          </span>
          <span style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--danger)", display: "inline-block" }} />
            Removed {diffNotes.filter((d) => d.status === "removed").length}
          </span>
          <span style={{ color: "var(--accent-2)", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent-2)", display: "inline-block" }} />
            Modified {diffNotes.filter((d) => d.status === "modified").length}
          </span>
        </div>
      )}
    </div>
  );
}
