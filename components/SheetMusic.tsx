"use client";

import { useEffect, useRef, useState } from "react";
import { measureIndexAt, measureGroupsForIndex } from "@/lib/measure";

type Props = {
  musicXml: string;
  className?: string;
  playheadTime?: number;
  isPlaying?: boolean;
  isScoreActive?: boolean;
  hasScorePlayback?: boolean;
  measureStarts?: number[];
  scoreDuration?: number | null;
  selectedMeasures?: { start: number; end: number } | null;
  measureApproximate?: boolean;
  onSeek?: (seconds: number) => void;
  onSelectMeasures?: (start: number, end: number) => void;
};

/**
 * Insert a highlight rect into a staff group using its own bbox.
 * Returns true if inserted, false if bbox was zero-size.
 */
export function insertHighlightRect(
  group: SVGGraphicsElement,
  dataAttr: string,
  fill: string,
  fillOpacity: string,
  stroke: string,
  strokeWidth: string,
  strokeDasharray: string,
): boolean {
  if (group.querySelector(`[${dataAttr}]`)) return true;
  void (group as any).getBoundingClientRect?.();
  let box = group.getBBox();
  if (box.width === 0 && box.height === 0) {
    const svg = group.closest("svg");
    if (svg) {
      const gr = group.getBoundingClientRect();
      const sr = svg.getBoundingClientRect();
      if (gr.width > 0 && gr.height > 0) {
        box = { x: gr.left - sr.left, y: gr.top - sr.top, width: gr.width, height: gr.height } as DOMRect;
      }
    }
  }
  if (box.width === 0 && box.height === 0) return false;
  const NS = "http://www.w3.org/2000/svg";
  const rect = document.createElementNS(NS, "rect");
  rect.setAttribute(dataAttr, "true");
  rect.setAttribute("x", String(box.x));
  rect.setAttribute("y", String(box.y));
  rect.setAttribute("width", String(box.width));
  rect.setAttribute("height", String(box.height));
  rect.setAttribute("fill", fill);
  rect.setAttribute("fill-opacity", fillOpacity);
  rect.setAttribute("stroke", stroke);
  rect.setAttribute("stroke-width", strokeWidth);
  rect.setAttribute("stroke-dasharray", strokeDasharray);
  rect.setAttribute("rx", "4");
  rect.setAttribute("pointer-events", "none");
  group.insertBefore(rect, group.firstChild);
  return true;
}

interface NoteEvent {
  startTime: number;
  endTime: number;
  svgGroup: SVGGElement;
  noteheads: HTMLElement[];
}

/**
 * Build a sorted list of note events from OSMD's graphical data model.
 * Each entry maps a note's notation-domain time range to its SVG elements.
 */
function buildNoteEvents(osmd: any, measureStarts: number[]): NoteEvent[] {
  const events: NoteEvent[] = [];
  if (!osmd?.GraphicSheet?.MeasureList || !measureStarts.length) return events;

  const measureList = osmd.GraphicSheet.MeasureList as any[][];
  const rules = osmd.rules;

  for (let mi = 0; mi < measureList.length; mi++) {
    const measureStart = measureStarts[mi];
    if (measureStart == null) continue;

    for (const gMeasure of measureList[mi]) {
      if (!gMeasure?.graphicalVoiceEntries) continue;
      for (const gve of gMeasure.graphicalVoiceEntries) {
        if (!gve?.notes) continue;
        for (const gNote of gve.notes) {
          try {
            const sourceNote = gNote?.sourceNote;
            if (!sourceNote) continue;

            // Get timing from source note
            const absTimestamp = sourceNote.ParentVoiceEntry?.ParentSourceStaffEntry?.AbsoluteTimestamp;
            if (!absTimestamp) continue;

            const noteLength = sourceNote.Length;
            if (!noteLength) continue;

            const noteStart = measureStart + absTimestamp.RealValue * (60 / (osmd.Sheet?.PlaybackSettings?.bpm || 120));
            const noteDuration = noteLength.RealValue * (60 / (osmd.Sheet?.PlaybackSettings?.bpm || 120));
            const noteEnd = noteStart + noteDuration;

            // Get SVG elements
            const noteheads = gNote.getNoteheadSVGs?.() ?? [];
            if (noteheads.length === 0) continue;

            events.push({ startTime: noteStart, endTime: noteEnd, svgGroup: gNote.getSVGGElement?.(), noteheads });
          } catch {
            // Skip notes that can't be mapped
          }
        }
      }
    }
  }

  events.sort((a, b) => a.startTime - b.startTime);
  return events;
}

/**
 * Find all note events that are sounding at the given time.
 * Uses binary search since events are sorted by startTime.
 */
function findActiveNotes(events: NoteEvent[], time: number): NoteEvent[] {
  const active: NoteEvent[] = [];
  for (const evt of events) {
    if (evt.startTime > time) break; // sorted, no need to continue
    if (time >= evt.startTime && time < evt.endTime) {
      active.push(evt);
    }
  }
  return active;
}

export default function SheetMusic({
  musicXml,
  className,
  playheadTime = 0,
  isPlaying = false,
  isScoreActive = false,
  hasScorePlayback = false,
  measureStarts,
  selectedMeasures,
  measureApproximate = false,
  onSeek,
  onSelectMeasures,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<any>(null);
  const currentMeasureRef = useRef(-1);
  const playbackMeasureRef = useRef(-1);
  const playbackRafRef = useRef(0);
  const cursorLineRef = useRef<SVGLineElement | null>(null);
  const noteEventsRef = useRef<NoteEvent[]>([]);
  const activeNotesRef = useRef<Set<HTMLElement>>(new Set());
  const anchorMeasureRef = useRef<number | null>(null);
  const [osmdReady, setOsmdReady] = useState(false);

  // ── OSMD initialization ────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || !musicXml) return;

    let cancelled = false;
    setOsmdReady(false);
    anchorMeasureRef.current = null;

    async function render() {
      const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
      if (cancelled || !containerRef.current) return;

      containerRef.current.innerHTML = "";

      const osmd = new OpenSheetMusicDisplay(containerRef.current, {
        autoResize: true,
        backend: "svg",
        drawTitle: false,
        drawSubtitle: false,
        drawCredits: false,
        drawPartNames: false,
        drawPartAbbreviations: false,
        drawMeasureNumbers: true,
        drawTimeSignatures: true,
        followCursor: false,
        autoBeam: false,
        pageFormat: "Endless",
        drawingParameters: "compacttight",
      });
      osmdRef.current = osmd;
      currentMeasureRef.current = -1;

      try {
        await osmd.load(musicXml);
        if (!cancelled) {
          osmd.render();
          // Hide the default OSMD cursor — we render our own
          osmd.cursor.show();
          osmd.cursor.cursorElement.style.display = "none";
          setOsmdReady(true);
        }
      } catch (err) {
        console.error("OSMD render failed:", err);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML =
            '<p style="color:var(--muted);text-align:center;padding:var(--s-4)">Could not render sheet music.</p>';
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [musicXml]);

  // ── Build note event map after OSMD renders ────────────────────────────────
  useEffect(() => {
    if (!osmdReady || !measureStarts?.length) {
      noteEventsRef.current = [];
      return;
    }
    const osmd = osmdRef.current;
    if (!osmd) return;
    // Build after a tick to ensure SVG is fully laid out
    const timer = setTimeout(() => {
      noteEventsRef.current = buildNoteEvents(osmd, measureStarts);
    }, 100);
    return () => clearTimeout(timer);
  }, [osmdReady, measureStarts]);

  // ── Continuous playback animation (cursor + note highlights) ───────────────
  useEffect(() => {
    const container = containerRef.current;
    const osmd = osmdRef.current;
    if (!osmdReady || !container || !osmd?.GraphicSheet) return;
    if (!isScoreActive || !measureStarts?.length) {
      // Remove cursor and note highlights
      cursorLineRef.current?.remove();
      cursorLineRef.current = null;
      for (const el of activeNotesRef.current) {
        el.classList.remove("score-note-active");
      }
      activeNotesRef.current.clear();
      return;
    }

    const NS = "http://www.w3.org/2000/svg";
    const svg = container.querySelector("svg");
    if (!svg) return;

    // Create cursor line if it doesn't exist
    if (!cursorLineRef.current) {
      const line = document.createElementNS(NS, "line");
      line.setAttribute("data-score-cursor", "true");
      line.setAttribute("stroke", "var(--score-playback)");
      line.setAttribute("stroke-width", "2");
      line.setAttribute("stroke-linecap", "round");
      line.setAttribute("pointer-events", "none");
      line.setAttribute("y1", "0");
      svg.appendChild(line);
      cursorLineRef.current = line;
    }

    const svgEl = svg;

    let rafId = 0;
    let prevMeasureIdx = -1;

    function animate() {
      const time = playheadTime;
      const measureIdx = measureIndexAt(measureStarts!, time);
      if (measureIdx < 0) {
        cursorLineRef.current!.setAttribute("visibility", "hidden");
        rafId = requestAnimationFrame(animate);
        return;
      }

      // ── Position cursor using OSMD's timestamp-to-X mapping ──
      try {
        const measureStart = measureStarts![measureIdx];
        const offset = time - measureStart;
        // Convert seconds to beats: beats = offset * bpm / 60
        const bpm = osmd.Sheet?.PlaybackSettings?.bpm || 120;
        const beatsInMeasure = offset * bpm / 60;
        // Get the measure's absolute timestamp and add the beat offset
        const Fraction = (osmd.GraphicSheet as any).MeasureList?.[0]?.[0]?.PositionAndShape?.AbsolutePosition
          ? null : null; // We'll use a different approach
        // Use OSMD's calculateXPositionFromTimestamp if available
        const graphicSheet = osmd.GraphicSheet;
        if (graphicSheet?.calculateXPositionFromTimestamp) {
          // Build a Fraction-like object for the timestamp
          const totalBeats = time * bpm / 60;
          // OSMD Fraction: we need to construct it properly
          // The Fraction class constructor: new Fraction(numerator, denominator)
          // For totalBeats beats, the timestamp in whole notes is totalBeats / 4 (in 4/4)
          // But OSMD uses its own internal Fraction. Let's try to use the iterator approach.
          const cursor = osmd.cursor;
          if (cursor?.iterator) {
            // Advance cursor to the right measure
            if (measureIdx !== prevMeasureIdx) {
              cursor.reset();
              for (let i = 0; i < measureIdx; i++) cursor.nextMeasure();
              prevMeasureIdx = measureIdx;
            }
            // Now advance note-by-note within the measure until we pass the current time
            const iter = cursor.iterator;
            while (!iter.EndReached) {
              const iterTime = measureStarts![iter.CurrentMeasureIndex] +
                (iter.CurrentSourceTimestamp?.RealValue || 0) * 60 / bpm;
              if (iterTime > time) break;
              if (iter.CurrentMeasureIndex > measureIdx) break;
              try { cursor.next(); } catch { break; }
            }

            // Position cursor at current note's X
            const gNotes = cursor.GNotesUnderCursor();
            if (gNotes?.length > 0) {
              const firstNote = gNotes[0] as any;
              const noteSvg = firstNote.getSVGGElement?.();
              if (noteSvg) {
                const noteRect = noteSvg.getBoundingClientRect();
                const svgRect = svgEl.getBoundingClientRect();
                const x = noteRect.left - svgRect.left;
                const systemTop = 0;
                const systemHeight = svgRect.height;
                cursorLineRef.current!.setAttribute("x1", String(x));
                cursorLineRef.current!.setAttribute("x2", String(x));
                cursorLineRef.current!.setAttribute("y1", String(systemTop));
                cursorLineRef.current!.setAttribute("y2", String(systemHeight));
                cursorLineRef.current!.setAttribute("visibility", "visible");
              }
            }

            // ── Highlight sounding notes ──
            // Clear previous highlights
            for (const el of activeNotesRef.current) {
              el.classList.remove("score-note-active");
            }
            activeNotesRef.current.clear();

            // Find notes at current position
            const currentNotes = cursor.NotesUnderCursor();
            if (currentNotes?.length > 0) {
              for (const note of currentNotes) {
                try {
                  const gNote = osmd.rules?.GNote?.(note);
                  if (gNote?.getNoteheadSVGs) {
                    for (const nh of gNote.getNoteheadSVGs()) {
                      nh.classList.add("score-note-active");
                      activeNotesRef.current.add(nh);
                    }
                  }
                } catch { /* skip */ }
              }
            }
          }
        }
      } catch {
        // Positioning failed — hide cursor
        cursorLineRef.current?.setAttribute("visibility", "hidden");
      }

      rafId = requestAnimationFrame(animate);
    }

    rafId = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(rafId);
      for (const el of activeNotesRef.current) {
        el.classList.remove("score-note-active");
      }
      activeNotesRef.current.clear();
    };
  }, [osmdReady, isScoreActive, measureStarts, playheadTime]);

  // ── Measure-level playback highlight (secondary cue) ──────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;

    cancelAnimationFrame(playbackRafRef.current);
    playbackRafRef.current = 0;

    if (!isScoreActive || !measureStarts || measureStarts.length === 0) {
      container.querySelectorAll("[data-playback-highlight]").forEach((n) => n.remove());
      playbackMeasureRef.current = -1;
      return;
    }

    const measureIdx = measureIndexAt(measureStarts, playheadTime);
    if (measureIdx < 0) {
      container.querySelectorAll("[data-playback-highlight]").forEach((n) => n.remove());
      playbackMeasureRef.current = -1;
      return;
    }
    if (measureIdx === playbackMeasureRef.current) return;

    const groups = measureGroupsForIndex(container, measureIdx);
    if (groups.length === 0) return;

    const prevIdx = playbackMeasureRef.current;
    playbackMeasureRef.current = measureIdx;

    let allInserted = true;
    for (const group of groups) {
      if (!group.querySelector("[data-playback-highlight]")) {
        const ok = insertHighlightRect(group, "data-playback-highlight", "var(--score-playback)", "0.08", "var(--score-playback)", "1.5", "none");
        if (!ok) allInserted = false;
      }
    }

    const removeStale = () => {
      for (const el of container.querySelectorAll("[data-playback-highlight]")) {
        const parent = el.parentElement;
        if (!parent || !groups.includes(parent as unknown as SVGGElement)) {
          el.remove();
        }
      }
    };

    if (allInserted) {
      removeStale();
    } else {
      const maxFrames = 12;
      let frame = 0;
      let retryTimer = 0;
      const retry = () => {
        if (playbackMeasureRef.current !== measureIdx || !containerRef.current) return;
        let retryAllOk = true;
        for (const group of groups) {
          if (!group.querySelector("[data-playback-highlight]")) {
            const ok = insertHighlightRect(group, "data-playback-highlight", "var(--score-playback)", "0.08", "var(--score-playback)", "1.5", "none");
            if (!ok) retryAllOk = false;
          }
        }
        if (retryAllOk) removeStale();
        frame += 1;
        if (!retryAllOk && frame < maxFrames) {
          playbackRafRef.current = requestAnimationFrame(retry);
          retryTimer = window.setTimeout(retry, 50);
        }
      };
      playbackRafRef.current = requestAnimationFrame(retry);
      return () => { cancelAnimationFrame(playbackRafRef.current); clearTimeout(retryTimer); };
    }

    // Auto-scroll
    const firstGroup = groups[0];
    const cRect = container.getBoundingClientRect();
    const mRect = firstGroup.getBoundingClientRect();
    const margin = 48;
    if (mRect.top < cRect.top + margin || mRect.bottom > cRect.bottom - margin) {
      const bigJump = prevIdx < 0 || Math.abs(measureIdx - prevIdx) > 1;
      firstGroup.scrollIntoView({ behavior: bigJump ? "auto" : "smooth", block: "nearest" });
    }
  }, [osmdReady, isScoreActive, measureStarts, playheadTime]);

  // Cleanup on source change
  useEffect(() => {
    if (isScoreActive) return;
    const container = containerRef.current;
    if (!container) return;
    cancelAnimationFrame(playbackRafRef.current);
    playbackRafRef.current = 0;
    cursorLineRef.current?.remove();
    cursorLineRef.current = null;
    container.querySelectorAll("[data-playback-highlight]").forEach((n) => n.remove());
    playbackMeasureRef.current = -1;
  }, [isScoreActive]);

  useEffect(() => { return () => { cancelAnimationFrame(playbackRafRef.current); }; }, []);

  // ── Selection highlight ────────────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container.querySelectorAll("[data-selection-highlight]").forEach((node) => node.remove());
    if (!selectedMeasures || !measureStarts || measureStarts.length === 0) return;

    for (let idx = selectedMeasures.start; idx <= selectedMeasures.end; idx += 1) {
      const groups = measureGroupsForIndex(container, idx);
      for (const group of groups) {
        insertHighlightRect(group, "data-selection-highlight", "#bd513a", measureApproximate ? "0.12" : "0.18", "#bd513a", "1.5", measureApproximate ? "4 3" : "none");
      }
    }
  }, [osmdReady, selectedMeasures, measureApproximate, measureStarts]);

  // ── Click handler ──────────────────────────────────────────────────────────
  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!measureStarts || measureStarts.length === 0) return;
    const container = containerRef.current;
    if (!container) return;

    const allGroups = container.querySelectorAll("g.vf-measure");
    const seen = new Set<string>();
    for (const measureEl of allGroups) {
      const id = measureEl.getAttribute("id");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const rect = measureEl.getBoundingClientRect();
      if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) {
        const index = Number(id) - 1;
        if (index >= 0 && measureStarts[index] != null) {
          if (isScoreActive && onSeek) onSeek(measureStarts[index]);
          if (onSelectMeasures) {
            const anchor = anchorMeasureRef.current;
            const rangeStart = event.shiftKey && anchor !== null ? Math.min(anchor, index) : index;
            const rangeEnd = event.shiftKey && anchor !== null ? Math.max(anchor, index) : index;
            onSelectMeasures(rangeStart, rangeEnd);
            anchorMeasureRef.current = index;
          }
        }
        return;
      }
    }
  }

  if (!musicXml) {
    return <p className="muted" style={{ textAlign: "center", padding: "var(--s-4)" }}>No sheet music data available.</p>;
  }

  const hint = !hasScorePlayback
    ? "Score playback is not available for this piece yet."
    : isScoreActive
      ? "Playing the score rendition in notation time. Click a measure to jump or select it."
      : "Select Score rendition in the transport to hear this notation (notation time).";

  return (
    <>
      <p className="sheet-music-hint">{hint}</p>
      <div
        ref={containerRef}
        className={`sheet-music-container ${className ?? ""}`}
        onClick={handleClick}
        style={{
          overflow: "auto",
          maxHeight: 640,
          background: "#f8f8f8",
          borderRadius: "var(--r-md)",
          padding: "var(--s-4)",
          border: "1px solid var(--border-strong)",
          cursor: measureStarts && measureStarts.length > 0 ? "pointer" : "default",
        }}
      />
    </>
  );
}
