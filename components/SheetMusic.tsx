"use client";

import { useEffect, useRef, useState } from "react";
import { measureIndexAt, measureGroupsForIndex } from "@/lib/measure";
import { annotationToMeasureRange, ANNOTATION_COLORS } from "@/lib/analysis-annotations";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

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
  annotations?: AnalysisAnnotation[];
  focusedAnnotationId?: string | null;
  onSeek?: (seconds: number) => void;
  onSelectMeasures?: (start: number, end: number) => void;
  onAnnotationClick?: (annotation: AnalysisAnnotation) => void;
};

/** Insert an overlay inside the actual OSMD measure bounds. */
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
  let box = group.getBBox();
  if (box.width === 0 && box.height === 0) return false;

  // OSMD measure groups include barline/staff extents. Keep overlays slightly
  // inset so selection never visually spills beyond the real measure boundary.
  const insetX = Math.min(1.5, box.width / 8);
  const insetY = Math.min(0.75, box.height / 10);
  box = {
    x: box.x + insetX,
    y: box.y + insetY,
    width: Math.max(0, box.width - insetX * 2),
    height: Math.max(0, box.height - insetY * 2),
  } as DOMRect;
  if (box.width === 0 || box.height === 0) return false;

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
  rect.setAttribute("rx", "2");
  rect.setAttribute("pointer-events", "none");
  group.insertBefore(rect, group.firstChild);
  return true;
}

function svgPoint(svg: SVGSVGElement, clientX: number, clientY: number) {
  const matrix = svg.getScreenCTM();
  if (!matrix) return null;
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  return point.matrixTransform(matrix.inverse());
}

function unionClientRect(groups: SVGGraphicsElement[]) {
  const rects = groups.map((group) => group.getBoundingClientRect()).filter((rect) => rect.width > 0 && rect.height > 0);
  if (rects.length === 0) return null;
  return {
    left: Math.min(...rects.map((rect) => rect.left)),
    right: Math.max(...rects.map((rect) => rect.right)),
    top: Math.min(...rects.map((rect) => rect.top)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  };
}

export default function SheetMusic({
  musicXml,
  className,
  playheadTime = 0,
  isScoreActive = false,
  hasScorePlayback = false,
  measureStarts,
  scoreDuration,
  selectedMeasures,
  measureApproximate = false,
  annotations,
  focusedAnnotationId,
  onSeek,
  onSelectMeasures,
  onAnnotationClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<any>(null);
  const cursorLineRef = useRef<SVGLineElement | null>(null);
  const playbackMeasureRef = useRef(-1);
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
        followCursor: false,
        autoBeam: false,
        pageFormat: "Endless",
        drawingParameters: "compacttight",
      });
      osmdRef.current = osmd;

      try {
        await osmd.load(musicXml);
        if (cancelled) return;
        osmd.render();
        osmd.cursor.show();
        osmd.cursor.cursorElement.style.display = "none";
        setOsmdReady(true);
      } catch (err) {
        console.error("OSMD render failed:", err);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = '<p class="score-render-error">Could not render this score.</p>';
        }
      }
    }

    void render();
    return () => { cancelled = true; };
  }, [musicXml]);

  // Playback follows the score using the measured OSMD geometry. This avoids
  // depending on the internal OSMD cursor iterator, which was resetting on
  // every React playhead update and often left no visible cursor at all.
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container || !measureStarts?.length || !isScoreActive) {
      cursorLineRef.current?.remove();
      cursorLineRef.current = null;
      container?.querySelectorAll("[data-playback-highlight]").forEach((node) => node.remove());
      playbackMeasureRef.current = -1;
      return;
    }

    const measureIdx = measureIndexAt(measureStarts, playheadTime);
    if (measureIdx < 0) return;
    const groups = measureGroupsForIndex(container, measureIdx);
    if (groups.length === 0) return;

    const svg = container.querySelector("svg");
    const bounds = unionClientRect(groups);
    if (!svg || !bounds) return;

    const start = measureStarts[measureIdx];
    const nextStart = measureStarts[measureIdx + 1];
    const previousSpan = measureIdx > 0 ? start - measureStarts[measureIdx - 1] : 0;
    const end = nextStart ?? scoreDuration ?? (start + (previousSpan > 0 ? previousSpan : 2));
    const progress = end > start ? Math.max(0, Math.min(1, (playheadTime - start) / (end - start))) : 0;
    const xClient = bounds.left + (bounds.right - bounds.left) * progress;
    const top = svgPoint(svg, xClient, bounds.top);
    const bottom = svgPoint(svg, xClient, bounds.bottom);
    if (!top || !bottom) return;

    if (!cursorLineRef.current) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("data-score-cursor", "true");
      line.setAttribute("stroke", "var(--score-playback)");
      line.setAttribute("stroke-width", "1.7");
      line.setAttribute("stroke-linecap", "round");
      line.setAttribute("pointer-events", "none");
      svg.appendChild(line);
      cursorLineRef.current = line;
    }
    const line = cursorLineRef.current;
    line.setAttribute("x1", String(top.x));
    line.setAttribute("x2", String(bottom.x));
    line.setAttribute("y1", String(top.y));
    line.setAttribute("y2", String(bottom.y));
    line.setAttribute("visibility", "visible");

    if (playbackMeasureRef.current !== measureIdx) {
      container.querySelectorAll("[data-playback-highlight]").forEach((node) => node.remove());
      for (const group of groups) {
        insertHighlightRect(group, "data-playback-highlight", "var(--score-playback)", "0.045", "var(--score-playback)", "0.6", "none");
      }
      const previousMeasure = playbackMeasureRef.current;
      playbackMeasureRef.current = measureIdx;

      const first = groups[0];
      const containerRect = container.getBoundingClientRect();
      const measureRect = first.getBoundingClientRect();
      const margin = 64;
      if (measureRect.top < containerRect.top + margin || measureRect.bottom > containerRect.bottom - margin) {
        const jumped = previousMeasure < 0 || Math.abs(measureIdx - previousMeasure) > 1;
        first.scrollIntoView({ behavior: jumped ? "auto" : "smooth", block: "center" });
      }
    }
  }, [isScoreActive, measureStarts, osmdReady, playheadTime, scoreDuration]);

  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container.querySelectorAll("[data-selection-highlight]").forEach((node) => node.remove());
    if (!selectedMeasures || !measureStarts?.length) return;

    for (let idx = selectedMeasures.start; idx <= selectedMeasures.end; idx += 1) {
      const groups = measureGroupsForIndex(container, idx);
      for (const group of groups) {
        insertHighlightRect(
          group,
          "data-selection-highlight",
          "var(--accent)",
          measureApproximate ? "0.07" : "0.11",
          "var(--accent)",
          "0.9",
          measureApproximate ? "3 3" : "none",
        );
      }
    }
  }, [measureApproximate, measureStarts, osmdReady, selectedMeasures]);

  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container.querySelectorAll("[data-annotation-highlight]").forEach((node) => node.remove());
    if (!annotations?.length || !measureStarts?.length) return;

    for (const annotation of annotations) {
      const range = annotationToMeasureRange(annotation, measureStarts);
      if (!range) continue;
      const colors = ANNOTATION_COLORS[annotation.category];
      const focused = annotation.id === focusedAnnotationId;
      for (let idx = range.start; idx <= range.end; idx += 1) {
        for (const group of measureGroupsForIndex(container, idx)) {
          insertHighlightRect(
            group,
            "data-annotation-highlight",
            colors.fill,
            focused ? "0.12" : "0.045",
            colors.stroke,
            focused ? "1" : "0.45",
            "none",
          );
        }
      }
    }
  }, [annotations, focusedAnnotationId, measureStarts, osmdReady]);

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!measureStarts?.length) return;
    const container = containerRef.current;
    if (!container) return;

    const allGroups = container.querySelectorAll("g.vf-measure");
    const seen = new Set<string>();
    for (const measureEl of allGroups) {
      const id = measureEl.getAttribute("id");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const rect = measureEl.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) continue;

      const index = Number(id) - 1;
      if (index < 0 || measureStarts[index] == null) return;
      if (isScoreActive && onSeek) onSeek(measureStarts[index]);
      if (onSelectMeasures) {
        const anchor = anchorMeasureRef.current;
        const rangeStart = event.shiftKey && anchor !== null ? Math.min(anchor, index) : index;
        const rangeEnd = event.shiftKey && anchor !== null ? Math.max(anchor, index) : index;
        onSelectMeasures(rangeStart, rangeEnd);
        anchorMeasureRef.current = index;
      }
      if (onAnnotationClick && annotations) {
        const annotation = annotations.find((item) => {
          const range = annotationToMeasureRange(item, measureStarts);
          return range && index >= range.start && index <= range.end;
        });
        if (annotation) onAnnotationClick(annotation);
      }
      return;
    }
  }

  if (!musicXml) {
    return <p className="score-render-error">Score unavailable.</p>;
  }

  return (
    <div className="sheet-music-wrap">
      <div
        ref={containerRef}
        className={`sheet-music-container ${className ?? ""}`}
        onClick={handleClick}
        style={{ cursor: measureStarts?.length ? "pointer" : "default" }}
      />
    </div>
  );
}
