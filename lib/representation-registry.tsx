"use client";

import { useRef } from "react";
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
  analysis?: unknown;
  bpm?: number;
  playheadTime?: number;
  editable?: boolean;
  onNotesChange?: (notes: { pitch: number; start: number; end: number; velocity: number }[]) => void;
};

type Note = NonNullable<RepresentationProps["notes"]>[number];

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
  score: ({ musicxml }) => (
    <div className="representation-body">
      <SheetMusic musicXml={musicxml ?? ""} />
    </div>
  ),
  spectrogram: ({ audioUrl }) => <SpectrogramWrapper audioUrl={audioUrl} />,
  harmony: () => <Placeholder label="Harmony analysis coming soon" />,
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
