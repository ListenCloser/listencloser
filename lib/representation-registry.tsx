"use client";

import { useRef, useState, useEffect } from "react";
import type { ReactNode } from "react";
import type { RepresentationKind } from "@/lib/stores/workspace";
import PianoRoll from "@/components/PianoRoll";
import EditablePianoRoll from "@/components/workspace/EditablePianoRoll";
import SheetMusic from "@/components/SheetMusic";
import Visualizer from "@/components/Visualizer";
import Spectrogram from "@/components/Spectrogram";

export type RepresentationProps = {
  notes?: { pitch: number; start: number; end: number; velocity: number }[];
  musicxml?: string;
  audioUrl?: string;
  sourceUrl?: string;
  sourceLabel?: string;
  analysis?: unknown;
  bpm?: number;
  playheadTime?: number;
  editable?: boolean;
  onNotesChange?: (notes: { pitch: number; start: number; end: number; velocity: number }[]) => void;
};

type Note = NonNullable<RepresentationProps["notes"]>[number];

function ScoreWrapper({ sourceUrl }: { sourceUrl?: string }) {
  const [musicxml, setMusicxml] = useState<string | null>(null);

  useEffect(() => {
    if (!sourceUrl || !sourceUrl.startsWith("/api/")) { setMusicxml(""); return; }
    let c = false;
    fetch(sourceUrl).then(r => r.json()).then(d => { if (!c) setMusicxml(d.musicxml || ""); }).catch(() => { if (!c) setMusicxml(""); });
    return () => { c = true; };
  }, [sourceUrl]);

  if (musicxml === null) return <div className="representation-body"><div className="muted">Loading score...</div></div>;
  if (!musicxml) return <div className="representation-body"><div className="muted">Score not available</div></div>;
  return <SheetMusic musicXml={musicxml} />;
}

function WaveformWrapper({ audioUrl }: { audioUrl?: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  if (!audioUrl) {
    return (
      <div className="representation-body">
        <p className="muted">No audio URL provided for waveform.</p>
      </div>
    );
  }

  return (
    <div className="representation-body">
      <audio ref={audioRef} src={audioUrl} controls style={{ width: "100%", marginBottom: "var(--s-2)" }} />
      <Visualizer audioRef={audioRef} />
    </div>
  );
}

function SpectrogramWrapper({ audioUrl }: { audioUrl?: string }) {
  if (!audioUrl) {
    return (
      <div className="representation-body">
        <p className="muted">No audio URL provided for spectrogram.</p>
      </div>
    );
  }

  return (
    <div className="representation-body">
      <Spectrogram url={audioUrl} />
    </div>
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="representation-body">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          minHeight: 120,
          color: "var(--muted)",
          fontSize: "var(--fs-sm)",
        }}
      >
        {label}
      </div>
    </div>
  );
}

const renderers: Record<RepresentationKind, (props: RepresentationProps) => ReactNode> = {
  piano_roll: ({ notes, bpm, playheadTime, editable, onNotesChange }) => (
    <div className="representation-body">
      {editable ? (
        <EditablePianoRoll
          notes={(notes ?? []) as Note[]}
          bpm={bpm}
          playheadTime={playheadTime}
          editable
          onNotesChange={onNotesChange}
        />
      ) : (
        <PianoRoll notes={(notes ?? []) as Note[]} bpm={bpm} playheadTime={playheadTime} />
      )}
    </div>
  ),
  waveform: ({ audioUrl }) => <WaveformWrapper audioUrl={audioUrl} />,
  score: ({ sourceUrl }) => <ScoreWrapper sourceUrl={sourceUrl} />,
  spectrogram: ({ audioUrl }) => <SpectrogramWrapper audioUrl={audioUrl} />,
  harmony: ({ sourceLabel }) => <Placeholder label={sourceLabel || "Harmony analysis coming soon"} />,
  structure: () => <Placeholder label="Structure view coming soon" />,
  annotations: () => <Placeholder label="Annotations coming soon" />,
};

export function renderRepresentation(kind: RepresentationKind, props: RepresentationProps): ReactNode {
  const renderer = renderers[kind];
  if (!renderer) {
    return (
      <div className="representation-body">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            minHeight: 120,
            color: "var(--muted)",
            fontSize: "var(--fs-sm)",
          }}
        >
          Unknown representation: {kind}
        </div>
      </div>
    );
  }
  return renderer(props);
}
