"use client";

import { useRef, useEffect, useState, useCallback, useReducer } from "react";
import { pitchToName } from "@/lib/notes";

type Note = { pitch: number; start: number; end: number; velocity: number };

const PPQ = 16;
const ROW_H = 22;
const LABEL_W = 36;
const TOP_PAD = 14;
const RESIZE_HANDLE_W = 10;

type DragState = {
  type: "move" | "resize";
  noteIndex: number;
  original: Note;
  current: Note;
  startSvgX: number;
  startSvgY: number;
};

export default function EditablePianoRoll({
  notes,
  bpm = 120,
  playheadTime = 0,
  editable = false,
  onNotesChange,
}: {
  notes: Note[];
  bpm?: number;
  playheadTime?: number;
  editable?: boolean;
  onNotesChange?: (notes: Note[]) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const dragRef = useRef<DragState | null>(null);
  const [, forceRerender] = useReducer((x: number) => x + 1, 0);
  const [hoverCursor, setHoverCursor] = useState("default");
  const notesRef = useRef(notes);
  notesRef.current = notes;
  const bpmRef = useRef(bpm);
  bpmRef.current = bpm;
  const svgDimsRef = useRef({ W: 0, h: 0 });

  const prevNotesPropRef = useRef(notes);
  useEffect(() => {
    if (prevNotesPropRef.current !== notes) {
      setSelectedIndex(-1);
    }
    prevNotesPropRef.current = notes;
  }, [notes]);

  if (!notes.length) return <p className="muted">No notes to display.</p>;

  const beatDur = 60 / bpm;

  const sorted = [...notes].sort((a, b) => a.start - b.start);
  const endTime = sorted.reduce((t, n) => Math.max(t, n.end), 0);
  const totalBeats = (endTime / 60) * bpm;
  const totalPx = Math.max(totalBeats * PPQ, 300);

  const minPitch = Math.min(...notes.map((n) => n.pitch));
  const maxPitch = Math.max(...notes.map((n) => n.pitch));

  const allPitches: number[] = [];
  for (let p = maxPitch; p >= minPitch; p--) {
    allPitches.push(p);
  }

  const rows: { pitch: number; label: string }[] = allPitches.map((p) => ({
    pitch: p,
    label: pitchToName(p),
  }));

  const h = rows.length * ROW_H + TOP_PAD;
  const W = LABEL_W + totalPx;
  svgDimsRef.current = { W, h };

  const playheadX = LABEL_W + (playheadTime / 60) * bpm * PPQ;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || playheadTime <= 0) return;
    const viewW = el.clientWidth;
    const target = Math.max(0, playheadX - viewW / 2);
    el.scrollLeft = target;
  }, [playheadX]);

  const clientToSvg = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      const dims = svgDimsRef.current;
      const sx = dims.W / rect.width;
      const sy = dims.h / rect.height;
      return { x: (clientX - rect.left) * sx, y: (clientY - rect.top) * sy };
    },
    []
  );

  const timeToX = useCallback(
    (t: number) => LABEL_W + (t / 60) * bpm * PPQ,
    [bpm]
  );

  const pitchToY = useCallback(
    (pitch: number) => (maxPitch - pitch) * ROW_H + TOP_PAD,
    [maxPitch]
  );

  const getNoteRect = useCallback(
    (note: Note) => {
      const x = timeToX(note.start);
      const dur = note.end - note.start;
      const w = Math.max((dur / 60) * bpm * PPQ, 5);
      const y = pitchToY(note.pitch);
      return { x, y, w, h: 14 };
    },
    [timeToX, pitchToY, bpm]
  );

  const findNoteAtPoint = useCallback(
    (svgX: number, svgY: number) => {
      const n = notesRef.current;
      for (let i = n.length - 1; i >= 0; i--) {
        const r = getNoteRect(n[i]);
        if (svgX >= r.x && svgX <= r.x + r.w && svgY >= r.y && svgY <= r.y + r.h) {
          return i;
        }
      }
      return -1;
    },
    [getNoteRect]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!editable) return;
      const pt = clientToSvg(e.clientX, e.clientY);
      const hitIndex = findNoteAtPoint(pt.x, pt.y);

      if (hitIndex >= 0) {
        const note = notesRef.current[hitIndex];
        const rect = getNoteRect(note);
        const onResizeEdge =
          hitIndex === selectedIndex &&
          pt.x >= rect.x + rect.w - RESIZE_HANDLE_W &&
          pt.x <= rect.x + rect.w + RESIZE_HANDLE_W;

        if (onResizeEdge) {
          dragRef.current = {
            type: "resize",
            noteIndex: hitIndex,
            original: { ...note },
            current: { ...note },
            startSvgX: pt.x,
            startSvgY: pt.y,
          };
          forceRerender();
        } else {
          setSelectedIndex(hitIndex);
          dragRef.current = {
            type: "move",
            noteIndex: hitIndex,
            original: { ...note },
            current: { ...note },
            startSvgX: pt.x,
            startSvgY: pt.y,
          };
          forceRerender();
        }
        e.preventDefault();
      } else {
        setSelectedIndex(-1);
        dragRef.current = null;
        forceRerender();
      }
    },
    [editable, clientToSvg, findNoteAtPoint, getNoteRect, selectedIndex]
  );

  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      const d = dragRef.current;

      if (!d) {
        if (!editable) return;
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        if (
          e.clientX < rect.left ||
          e.clientX > rect.right ||
          e.clientY < rect.top ||
          e.clientY > rect.bottom
        ) {
          setHoverCursor("default");
          return;
        }
        const pt = clientToSvg(e.clientX, e.clientY);
        const hitIndex = findNoteAtPoint(pt.x, pt.y);
        if (hitIndex >= 0 && hitIndex === selectedIndex) {
          const note = notesRef.current[hitIndex];
          const r = getNoteRect(note);
          if (
            pt.x >= r.x + r.w - RESIZE_HANDLE_W &&
            pt.x <= r.x + r.w + RESIZE_HANDLE_W
          ) {
            setHoverCursor("ew-resize");
          } else {
            setHoverCursor("pointer");
          }
        } else if (hitIndex >= 0) {
          setHoverCursor("pointer");
        } else {
          setHoverCursor("default");
        }
        return;
      }

      const pt = clientToSvg(e.clientX, e.clientY);
      const dx = pt.x - d.startSvgX;
      const dy = pt.y - d.startSvgY;
      const bd = 60 / bpmRef.current;

      if (d.type === "move") {
        const dt = (dx / PPQ) * bd;
        const dp = Math.round(dy / ROW_H);
        d.current = {
          ...d.original,
          start: Math.max(0, d.original.start + dt),
          pitch: Math.min(maxPitch, Math.max(minPitch, d.original.pitch - dp)),
        };
      } else {
        const dt = (dx / PPQ) * bd;
        d.current = {
          ...d.original,
          end: Math.max(d.original.start + 0.01, d.original.end + dt),
        };
      }
      setHoverCursor(d.type === "resize" ? "ew-resize" : "grabbing");
      forceRerender();
    };

    const handleUp = () => {
      const d = dragRef.current;
      if (!d) return;
      const updatedNotes = notesRef.current.map((n, i) =>
        i === d.noteIndex ? d.current : n
      );
      dragRef.current = null;
      forceRerender();
      onNotesChange?.(updatedNotes);
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [editable, selectedIndex, clientToSvg, findNoteAtPoint, getNoteRect, maxPitch, minPitch, onNotesChange]);

  useEffect(() => {
    if (!editable || selectedIndex < 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      if (dragRef.current) return;
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      const newNotes = notesRef.current.filter((_, i) => i !== selectedIndex);
      onNotesChange?.(newNotes);
      setSelectedIndex(-1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [editable, selectedIndex, onNotesChange]);

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!editable || !onNotesChange) return;
      const pt = clientToSvg(e.clientX, e.clientY);
      const hitIndex = findNoteAtPoint(pt.x, pt.y);
      if (hitIndex >= 0) return;

      const bd = 60 / bpm;
      const t = ((pt.x - LABEL_W) / (bpm * PPQ)) * 60;
      const pitchIdx = Math.round((pt.y - TOP_PAD) / ROW_H);
      const pitch = maxPitch - pitchIdx;
      const clampedPitch = Math.min(maxPitch, Math.max(minPitch, pitch));

      const newNote: Note = {
        pitch: clampedPitch,
        start: Math.max(0, t),
        end: Math.max(0, t) + 0.25 * bd,
        velocity: 64,
      };

      onNotesChange([...notes, newNote]);
    },
    [editable, onNotesChange, clientToSvg, findNoteAtPoint, bpm, maxPitch, minPitch, notes]
  );

  const dragState = dragRef.current;

  const isSelected = (index: number) => index === selectedIndex;
  const displayNote = (note: Note, index: number): Note => {
    if (dragState && dragState.noteIndex === index) return dragState.current;
    return note;
  };

  return (
    <div className="piano-roll-container" data-testid="editable-piano-roll">
      <div className="piano-roll-scroll" ref={scrollRef}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${h}`}
          preserveAspectRatio="xMinYMin meet"
          width="100%"
          height={h}
          style={{
            display: "block",
            cursor: editable ? hoverCursor : undefined,
            userSelect: "none",
          }}
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClick}
        >
          <rect x={0} y={0} width={LABEL_W} height={h} fill="var(--panel-2)" />

          {rows.map((row, ri) => (
            <rect
              key={`stripe-${row.pitch}`}
              x={LABEL_W}
              y={ri * ROW_H + TOP_PAD}
              width={totalPx}
              height={ROW_H}
              fill={ri % 2 === 0 ? "var(--panel-2)" : "transparent"}
            />
          ))}

          {Array.from({ length: Math.floor(totalBeats) + 1 }, (_, i) => {
            const x = LABEL_W + i * PPQ;
            const isMeasure = i % 4 === 0;
            return (
              <line
                key={i}
                x1={x}
                y1={0}
                x2={x}
                y2={h}
                stroke={isMeasure ? "var(--border-strong)" : "var(--border)"}
                strokeWidth={isMeasure ? 1.5 : 0.5}
              />
            );
          })}

          {rows.map((row, ri) => {
            const y = ri * ROW_H + TOP_PAD;
            const rowNotes = notes.map((n, i) => ({ note: displayNote(n, i), index: i })).filter(
              ({ note: n }) => n.pitch === row.pitch
            );

            return (
              <g key={row.pitch}>
                <text
                  x={4}
                  y={y + 15}
                  fill="var(--muted)"
                  fontSize={11}
                  fontFamily="var(--font-mono)"
                  style={{ pointerEvents: "none" }}
                >
                  {row.label}
                </text>
                {rowNotes.map(({ note: n, index: ni }) => {
                  const x = timeToX(n.start);
                  const dur = n.end - n.start;
                  const w = Math.max((dur / 60) * bpm * PPQ, 5);
                  const active =
                    playheadTime >= n.start && playheadTime <= n.end;
                  const selected = isSelected(ni);
                  return (
                    <g key={ni}>
                      <rect
                        x={x}
                        y={y}
                        width={w}
                        height={14}
                        rx={4}
                        fill={
                          selected ? "var(--accent-strong)" : "var(--accent)"
                        }
                        opacity={
                          selected
                            ? 0.85
                            : active
                              ? 0.95
                              : 0.25 + (n.velocity / 127) * 0.45
                        }
                        stroke={
                          selected ? "var(--text)" : undefined
                        }
                        strokeWidth={selected ? 1.5 : undefined}
                        style={
                          selected
                            ? {
                                filter:
                                  "drop-shadow(0 0 10px var(--accent))",
                              }
                            : active
                              ? {
                                  filter:
                                    "drop-shadow(0 0 5px var(--accent))",
                                }
                              : undefined
                        }
                      >
                        <title>
                          {row.label} @ {n.start.toFixed(2)}s · vel{" "}
                          {n.velocity}
                        </title>
                      </rect>
                      {selected && (
                        <polygon
                          points={`${x + w + 2},${y + 4} ${x + w + RESIZE_HANDLE_W},${y + 7} ${x + w + 2},${y + 10}`}
                          fill="var(--text)"
                          opacity={0.7}
                        />
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}

          {playheadTime > 0 && playheadX <= W && (
            <g style={{ pointerEvents: "none" }}>
              <line
                x1={playheadX}
                y1={0}
                x2={playheadX}
                y2={h}
                stroke="var(--accent-strong)"
                strokeWidth={1.5}
              />
              <polygon
                points={`${playheadX},0 ${playheadX + 6},${TOP_PAD - 4} ${playheadX},${TOP_PAD} ${playheadX - 6},${TOP_PAD - 4}`}
                fill="var(--accent-strong)"
              />
            </g>
          )}
        </svg>
      </div>
      <div className="piano-roll-footer">
        <span className="muted">
          {notes.length} notes · {endTime.toFixed(1)}s
        </span>
        {playheadTime > 0 && (
          <span className="muted">{playheadTime.toFixed(1)}s</span>
        )}
      </div>
    </div>
  );
}
