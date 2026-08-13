"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  musicXml: string;
  className?: string;
  playheadTime?: number;
  isScoreActive?: boolean;
  hasScorePlayback?: boolean;
  measureStarts?: number[];
  onSeek?: (seconds: number) => void;
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
  onSeek,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<any>(null);
  const currentMeasureRef = useRef(-1);
  const [osmdReady, setOsmdReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !musicXml) return;

    let cancelled = false;
    setOsmdReady(false);

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

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!onSeek || !isScoreActive || !measureStarts || measureStarts.length === 0) return;
    const container = containerRef.current;
    if (!container) return;
    // Map the click to the engraved measure whose bounding box contains it,
    // avoiding the OSMD internal coordinate transform entirely.
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
          onSeek(measureStarts[index]);
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
      ? "Playing the score in notation time. Click a measure to jump."
      : "Select Score in the transport to hear this notation (notation time).";

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
          cursor: isScoreActive && measureStarts && measureStarts.length > 0 ? "pointer" : "default",
        }}
      />
    </>
  );
}
