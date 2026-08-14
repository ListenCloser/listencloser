"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  musicXml: string;
  className?: string;
  playheadTime?: number;
  isScoreActive?: boolean;
  hasScorePlayback?: boolean;
  measureStarts?: number[];
  scoreDuration?: number | null;
  selectedMeasures?: { start: number; end: number } | null;
  measureApproximate?: boolean;
  onSeek?: (seconds: number) => void;
  onSelectMeasures?: (start: number, end: number) => void;
};

function measureIndexAt(starts: number[], time: number): number {
  let index = 0;
  for (let i = 0; i < starts.length; i += 1) {
    if (starts[i] <= time) index = i;
    else break;
  }
  return index;
}

export default function SheetMusic({
  musicXml,
  className,
  playheadTime = 0,
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
  const anchorMeasureRef = useRef<number | null>(null);
  const [osmdReady, setOsmdReady] = useState(false);

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
        followCursor: true,
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
          osmd.cursor.show();
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

    return () => {
      cancelled = true;
    };
  }, [musicXml]);

  useEffect(() => {
    const osmd = osmdRef.current;
    if (!osmdReady || !osmd?.cursor) return;

    if (!isScoreActive || !measureStarts || measureStarts.length === 0) {
      currentMeasureRef.current = -1;
      return;
    }

    const target = Math.min(measureIndexAt(measureStarts, playheadTime), measureStarts.length - 1);
    if (target === currentMeasureRef.current) return;

    let from = currentMeasureRef.current;
    if (from < 0 || target < from) {
      osmd.cursor.reset();
      from = 0;
    }
    const steps = Math.max(0, target - from);
    for (let i = 0; i < steps; i += 1) osmd.cursor.nextMeasure();
    currentMeasureRef.current = target;
  }, [osmdReady, isScoreActive, measureStarts, playheadTime]);

  // Highlight the selected measures by inserting a translucent rect into each
  // measure group's SVG user space (getBBox), so it tracks the engraved layout
  // exactly regardless of CSS scaling. Re-applied on render and selection change.
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container.querySelectorAll("[data-selection-highlight]").forEach((node) => node.remove());
    if (!selectedMeasures || !measureStarts || measureStarts.length === 0) return;

    const NS = "http://www.w3.org/2000/svg";
    const measures = container.querySelectorAll("g.vf-measure");
    for (const measureEl of measures) {
      const index = Number(measureEl.getAttribute("id")) - 1;
      if (index < selectedMeasures.start || index > selectedMeasures.end) continue;
      const box = (measureEl as SVGGraphicsElement).getBBox();
      if (box.width === 0 && box.height === 0) continue;
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("data-selection-highlight", "true");
      rect.setAttribute("x", String(box.x));
      rect.setAttribute("y", String(box.y));
      rect.setAttribute("width", String(box.width));
      rect.setAttribute("height", String(box.height));
      rect.setAttribute("fill", measureApproximate ? "#bd513a" : "#bd513a");
      rect.setAttribute("fill-opacity", measureApproximate ? "0.12" : "0.18");
      rect.setAttribute("stroke", "#bd513a");
      rect.setAttribute("stroke-width", "1.5");
      rect.setAttribute("stroke-dasharray", measureApproximate ? "4 3" : "none");
      rect.setAttribute("rx", "4");
      rect.setAttribute("pointer-events", "none");
      measureEl.insertBefore(rect, measureEl.firstChild);
    }
  }, [osmdReady, selectedMeasures, measureApproximate, measureStarts]);

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!measureStarts || measureStarts.length === 0) return;
    const container = containerRef.current;
    if (!container) return;
// Map the click to the engraved measure whose bounding box contains it,
// avoiding the OSMD internal coordinate transform entirely.
// ASSUMPTION: OSMD renders each measure as a <g class="vf-measure"> with an
// `id` attribute equal to the 1-based measure index (e.g., "1", "2", ...).
// This holds for single-part piano scores rendered with Endless page format.
// For multi-staff/grand-staff scores, VexFlow may generate separate measure
// elements per part/staff with different ID schemes. If that becomes a
// supported use case, this logic will need to be updated to use OSMD's
// `getMeasureList()` API or similar for stable measure identification.
const measures = container.querySelectorAll("g.vf-measure");
    for (const measureEl of measures) {
      const rect = measureEl.getBoundingClientRect();
      if (
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom
      ) {
        const index = Number(measureEl.getAttribute("id")) - 1;
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
    return (
      <p className="muted" style={{ textAlign: "center", padding: "var(--s-4)" }}>
        No sheet music data available.
      </p>
    );
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
