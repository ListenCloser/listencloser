"use client";

import { useEffect, useRef, useState } from "react";
import { measureIndexAt, measureGroupsForIndex, unionBBox } from "@/lib/measure";

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
  const autoScrollRef = useRef(true);
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

  // ── Playback highlight: one blue overlay on the current measure ───────────
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;

    container
      .querySelectorAll("[data-playback-highlight]")
      .forEach((n) => n.remove());

    if (!isScoreActive || !measureStarts || measureStarts.length === 0) {
      playbackMeasureRef.current = -1;
      return;
    }

    const measureIdx = measureIndexAt(measureStarts, playheadTime);
    if (measureIdx < 0) {
      playbackMeasureRef.current = -1;
      return;
    }
    if (measureIdx === playbackMeasureRef.current) return;

    const groups = measureGroupsForIndex(container, measureIdx);
    if (groups.length === 0) return;

    const box = unionBBox(groups);
    if (!box) return;

    const prevIdx = playbackMeasureRef.current;
    playbackMeasureRef.current = measureIdx;

    const NS = "http://www.w3.org/2000/svg";
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("data-playback-highlight", "true");
    rect.setAttribute("x", String(box.x));
    rect.setAttribute("y", String(box.y));
    rect.setAttribute("width", String(box.width));
    rect.setAttribute("height", String(box.height));
    rect.setAttribute("fill", "var(--score-playback)");
    rect.setAttribute("fill-opacity", "0.14");
    rect.setAttribute("stroke", "var(--score-playback)");
    rect.setAttribute("stroke-width", "2");
    rect.setAttribute("rx", "4");
    rect.setAttribute("pointer-events", "none");
    groups[0].insertBefore(rect, groups[0].firstChild);

    // Auto-scroll: only when the measure is outside the visible region.
    if (!autoScrollRef.current) return;
    const cRect = container.getBoundingClientRect();
    const mRect = groups[0].getBoundingClientRect();
    const margin = 48;
    if (mRect.top < cRect.top + margin || mRect.bottom > cRect.bottom - margin) {
      const bigJump = prevIdx < 0 || Math.abs(measureIdx - prevIdx) > 1;
      groups[0].scrollIntoView({
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
    container
      .querySelectorAll("[data-playback-highlight]")
      .forEach((n) => n.remove());
    playbackMeasureRef.current = -1;
  }, [isScoreActive]);

  // ── Selection highlight (existing behaviour, refactored for multi-staff) ──
  useEffect(() => {
    const container = containerRef.current;
    if (!osmdReady || !container) return;
    container
      .querySelectorAll("[data-selection-highlight]")
      .forEach((node) => node.remove());
    if (!selectedMeasures || !measureStarts || measureStarts.length === 0) return;

    const NS = "http://www.w3.org/2000/svg";
    for (
      let idx = selectedMeasures.start;
      idx <= selectedMeasures.end;
      idx += 1
    ) {
      const groups = measureGroupsForIndex(container, idx);
      const box = unionBBox(groups);
      if (!box) continue;
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("data-selection-highlight", "true");
      rect.setAttribute("x", String(box.x));
      rect.setAttribute("y", String(box.y));
      rect.setAttribute("width", String(box.width));
      rect.setAttribute("height", String(box.height));
      rect.setAttribute("fill", "#bd513a");
      rect.setAttribute(
        "fill-opacity",
        measureApproximate ? "0.12" : "0.18",
      );
      rect.setAttribute("stroke", "#bd513a");
      rect.setAttribute("stroke-width", "1.5");
      rect.setAttribute(
        "stroke-dasharray",
        measureApproximate ? "4 3" : "none",
      );
      rect.setAttribute("rx", "4");
      rect.setAttribute("pointer-events", "none");
      groups[0].insertBefore(rect, groups[0].firstChild);
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
