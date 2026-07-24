"use client";

import { useEffect, useRef } from "react";

type Props = {
  musicXml: string;
  className?: string;
};

export default function SheetMusic({ musicXml, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<unknown>(null);

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
      });
      osmdRef.current = osmd;

      try {
        await osmd.load(musicXml);
        if (!cancelled) osmd.render();
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
