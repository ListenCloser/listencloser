"use client";

import { useEffect, useRef, useState } from "react";
import { measureIndexAt, measureGroupsForIndex } from "@/lib/measure";

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

export function insertHighlightRect(
  group: SVGGraphicsElement,
  dataAttr: string,
  fill: string,
  fillOpacity: string,
  stroke: string,
  strokeWidth: string,
  strokeDasharray: string,
): boolean {
  // Guard against duplicate inserts.
  if (group.querySelector(`[${dataAttr}]`)) return true;
  // Force layout reflow so getBBox() returns valid geometry after DOM
  // mutations that may have invalidated the SVG layout tree.
  void (group as any).getBoundingClientRect?.();
  let box = group.getBBox();
  // getBBox() can return (0,0,0,0) before SVG layout settles.  Fall back
  // to getBoundingClientRect() relative to the nearest SVG ancestor.
  if (box.width === 0 && box.height === 0) {
    const svg = group.closest("svg");
    if (svg) {
      const gr = group.getBoundingClientRect();
      const sr = svg.getBoundingClientRect();
      if (gr.width > 0 && gr.height > 0) {
        box = {
          x: gr.left - sr.left,
          y: gr.top - sr.top,
          width: gr.width,
          height: gr.height,
        } as DOMRect;
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
  const playbackMeasureRef = useRef(-1);
  const playbackRafRef = useRef(0);
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

  // ── OSMD cursor: advance to the current measure ───────────────────────────
  useEffect(() => {
    const osmd = osmdRef.current;
    if (!osmdReady || !osmd?.cursor) return;

    if (!isScoreActive || !measureStarts || measureStarts.length === 0) {
      currentMeasureRef.current = -1;
      return;
    }

    const target = Math.min(
      Math.max(measureIndexAt(measureStarts, playheadTime), 0),
      measureStarts.length - 1,
    );
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

  // ── Playback highlight: one overlay per staff group ───────────────────────
  // Uses bounded requestAnimationFrame retries when getBBox() returns
  // zero-size (SVG layout not yet settled).  Cancels stale retries on
  // measure change, source change, rerender, and unmount.
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;

    cancelAnimationFrame(playbackRafRef.current);
    playbackRafRef.current = 0;

    if (!isScoreActive || !measureStarts || measureStarts.length === 0) {
      container
        .querySelectorAll("[data-playback-highlight]")
        .forEach((n) => n.remove());
      playbackMeasureRef.current = -1;
      return;
    }

    const measureIdx = measureIndexAt(measureStarts, playheadTime);
    if (measureIdx < 0) {
      container
        .querySelectorAll("[data-playback-highlight]")
        .forEach((n) => n.remove());
      playbackMeasureRef.current = -1;
      return;
    }
    if (measureIdx === playbackMeasureRef.current) return;

    const groups = measureGroupsForIndex(container, measureIdx);
    if (groups.length === 0) return;

    const prevIdx = playbackMeasureRef.current;
    playbackMeasureRef.current = measureIdx;

    // Attempt to insert the new highlight.  If getBBox() returns zero
    // (SVG layout not yet settled), schedule bounded retries.  Do NOT
    // remove the previous measure's highlight until the new one lands,
    // so the highlight is always at least partially visible.
    let allInserted = true;
    for (const group of groups) {
      if (!group.querySelector("[data-playback-highlight]")) {
        const ok = insertHighlightRect(
          group,
          "data-playback-highlight",
          "var(--score-playback)",
          "0.14",
          "var(--score-playback)",
          "2",
          "none",
        );
        if (!ok) allInserted = false;
      }
    }

    const removeStale = () => {
      for (const el of container.querySelectorAll(
        "[data-playback-highlight]",
      )) {
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
        if (playbackMeasureRef.current !== measureIdx || !containerRef.current)
          return;
        let retryAllOk = true;
        for (const group of groups) {
          if (!group.querySelector("[data-playback-highlight]")) {
            const ok = insertHighlightRect(
              group,
              "data-playback-highlight",
              "var(--score-playback)",
              "0.14",
              "var(--score-playback)",
              "2",
              "none",
            );
            if (!ok) retryAllOk = false;
          }
        }
        if (retryAllOk) {
          removeStale();
        }
        frame += 1;
        if (!retryAllOk && frame < maxFrames) {
          playbackRafRef.current = requestAnimationFrame(retry);
          retryTimer = window.setTimeout(retry, 50);
        }
      };
      playbackRafRef.current = requestAnimationFrame(retry);
      return () => {
        cancelAnimationFrame(playbackRafRef.current);
        clearTimeout(retryTimer);
      };
    }

    // Auto-scroll: use DOM client rects (viewport coordinates) to check
    // whether the first staff group is visible.  scrollIntoView with
    // block:"nearest" only scrolls when the element is outside the viewport.
    const firstGroup = groups[0];
    const cRect = container.getBoundingClientRect();
    const mRect = firstGroup.getBoundingClientRect();
    const margin = 48;
    if (
      mRect.top < cRect.top + margin ||
      mRect.bottom > cRect.bottom - margin
    ) {
      const bigJump = prevIdx < 0 || Math.abs(measureIdx - prevIdx) > 1;
      firstGroup.scrollIntoView({
        behavior: bigJump ? "auto" : "smooth",
        block: "nearest",
      });
    }
  }, [osmdReady, isScoreActive, measureStarts, playheadTime]);

  // Cleanup playback highlight when score becomes inactive or source changes.
  useEffect(() => {
    if (isScoreActive) return;
    const container = containerRef.current;
    if (!container) return;
    cancelAnimationFrame(playbackRafRef.current);
    playbackRafRef.current = 0;
    container
      .querySelectorAll("[data-playback-highlight]")
      .forEach((n) => n.remove());
    playbackMeasureRef.current = -1;
  }, [isScoreActive]);

  // Cancel pending RAF on unmount.
  useEffect(() => {
    return () => {
      cancelAnimationFrame(playbackRafRef.current);
    };
  }, []);

  // ── Selection highlight: one overlay per staff group ──────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container
      .querySelectorAll("[data-selection-highlight]")
      .forEach((node) => node.remove());
    if (!selectedMeasures || !measureStarts || measureStarts.length === 0)
      return;

    for (
      let idx = selectedMeasures.start;
      idx <= selectedMeasures.end;
      idx += 1
    ) {
      const groups = measureGroupsForIndex(container, idx);
      for (const group of groups) {
        insertHighlightRect(
          group,
          "data-selection-highlight",
          "#bd513a",
          measureApproximate ? "0.12" : "0.18",
          "#bd513a",
          "1.5",
          measureApproximate ? "4 3" : "none",
        );
      }
    }
  }, [osmdReady, selectedMeasures, measureApproximate, measureStarts]);

  // ── Measure click / selection ──────────────────────────────────────────────
  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!measureStarts || measureStarts.length === 0) return;
    const container = containerRef.current;
    if (!container) return;

    // Map the click to the engraved measure whose bounding box contains it,
    // handling multi-staff (grand-staff) scores where multiple g.vf-measure
    // elements share the same id — one per staff.  We check all groups and
    // take the first whose bounding rect contains the click point.
    const allGroups = container.querySelectorAll("g.vf-measure");
    const seen = new Set<string>();
    for (const measureEl of allGroups) {
      const id = measureEl.getAttribute("id");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const rect = measureEl.getBoundingClientRect();
      if (
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom
      ) {
        const index = Number(id) - 1;
        if (index >= 0 && measureStarts[index] != null) {
          if (isScoreActive && onSeek) onSeek(measureStarts[index]);
          if (onSelectMeasures) {
            const anchor = anchorMeasureRef.current;
            const rangeStart =
              event.shiftKey && anchor !== null
                ? Math.min(anchor, index)
                : index;
            const rangeEnd =
              event.shiftKey && anchor !== null
                ? Math.max(anchor, index)
                : index;
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
      <p
        className="muted"
        style={{ textAlign: "center", padding: "var(--s-4)" }}
      >
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
          cursor:
            measureStarts && measureStarts.length > 0 ? "pointer" : "default",
        }}
      />
    </>
  );
}
