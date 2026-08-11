"use client";

import { useEffect, useRef } from "react";

type Props = {
  musicXml: string;
  className?: string;
  playheadTime?: number;
  bpm?: number;
};

export default function SheetMusic({ musicXml, className, playheadTime = 0, bpm = 120 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<any>(null);
  const cursorStepRef = useRef(-1);

  useEffect(() => {
    if (!containerRef.current || !musicXml) return;

    let cancelled = false;

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
      });
      osmdRef.current = osmd;

      try {
        await osmd.load(musicXml);
        if (!cancelled) {
          osmd.render();
          osmd.cursor.show();
          cursorStepRef.current = 0;
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
    if (!osmd?.cursor || !Number.isFinite(playheadTime) || bpm <= 0) return;
    // OSMD's cursor is expressed in score timestamps. Until beat tracking is
    // persisted with the score, use the same MIDI tempo grid used by the piano
    // roll. This gives a visible, deterministic playback relationship without
    // pretending it is a perfect score-following alignment.
    const targetStep = Math.max(0, Math.floor(playheadTime * bpm / 60));
    try {
      if (targetStep < cursorStepRef.current) {
        osmd.cursor.reset();
        cursorStepRef.current = 0;
      }
      const steps = Math.min(targetStep - cursorStepRef.current, 64);
      for (let index = 0; index < steps; index += 1) osmd.cursor.next();
      if (steps > 0) cursorStepRef.current += steps;
    } catch {
      // Cursor support varies with MusicXML content; score rendering remains
      // usable even when a cursor cannot advance for a malformed draft.
    }
  }, [bpm, playheadTime]);

  if (!musicXml) {
    return (
      <p className="muted" style={{ textAlign: "center", padding: "var(--s-4)" }}>
        No sheet music data available.
      </p>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`sheet-music-container ${className ?? ""}`}
      style={{
        overflow: "auto",
        maxHeight: 500,
        background: "#f8f8f8",
        borderRadius: "var(--r-md)",
        padding: "var(--s-4)",
        border: "1px solid var(--border-strong)",
      }}
    />
  );
}
