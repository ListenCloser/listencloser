"use client";

import type { ReactNode } from "react";
import type { RepresentationKind } from "@/lib/stores/workspace";
import { renderRepresentation } from "@/lib/representation-registry";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

type Note = { pitch: number; start: number; end: number; velocity: number };

type RepresentationLaneProps = {
  kind: RepresentationKind;
  label: string;
  sourceLabel: string;
  confidence: number | null;
  isExpanded: boolean;
  onExpand: () => void;
  children?: ReactNode;
  footerControls?: ReactNode;
  workspaceNotes?: Note[] | null;
  musicxml?: string;
  audioUrl?: string;
  hideHeader?: boolean;
};

const KIND_GLYPHS: Record<RepresentationKind, string> = {
  piano_roll: "🎹",
  waveform: "〰",
  spectrogram: "🔥",
  score: "🎼",
  harmony: "♩",
  structure: "▦",
  annotations: "✎",
};

export default function RepresentationLane({
  kind,
  label,
  sourceLabel,
  confidence,
  isExpanded,
  onExpand,
  children,
  footerControls,
  workspaceNotes,
  musicxml,
  audioUrl,
  hideHeader = false,
}: RepresentationLaneProps) {
  const { transport, seek } = useTransport();
  const { timeline } = useTimeline();
  const glyph = KIND_GLYPHS[kind] ?? "▯";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-md)",
        background: "var(--panel)",
        overflow: "hidden",
        transition: "box-shadow var(--dur) var(--ease)",
        ...(isExpanded ? { flex: 1 } : { flexShrink: 0 }),
      }}
    >
      {!hideHeader && <button
        type="button"
        className="representation-header"
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? "Collapse" : "Expand"} ${label}`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-2)",
          padding: "var(--s-2) var(--s-3)",
          background: isExpanded ? "var(--panel-2)" : "var(--panel)",
          borderBottom: isExpanded ? "1px solid var(--border)" : undefined,
          minHeight: 38,
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={onExpand}
      >
        <span style={{ fontSize: 14, lineHeight: 1 }}>{glyph}</span>

        <span
          style={{
            fontSize: "var(--fs-sm)",
            fontWeight: "var(--fw-medium)",
            color: "var(--text)",
          }}
        >
          {label}
        </span>

        <span
          style={{
            fontSize: "var(--fs-xs)",
            color: "var(--muted)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {sourceLabel}
        </span>

        {confidence !== null && (
          <span
            className="badge"
            style={{
              fontSize: 10,
              padding: "2px 6px",
              background:
                confidence >= 0.8
                  ? "var(--success-soft)"
                  : confidence >= 0.5
                    ? "var(--accent-soft-2)"
                    : "var(--danger-soft)",
              color:
                confidence >= 0.8
                  ? "var(--success)"
                  : confidence >= 0.5
                    ? "var(--accent-2)"
                    : "var(--danger)",
            }}
          >
            {Math.round(confidence * 100)}%
          </span>
        )}

        <span aria-hidden="true" style={{ marginLeft: "auto", color: "var(--muted)" }}>{isExpanded ? "▾" : "▸"}</span>
      </button>}

      {isExpanded && (
        <>
          <div
            style={{
              flex: 1,
              overflow: "auto",
              padding: children ? "var(--s-3)" : undefined,
            }}
            >
              {children || renderRepresentation(kind, {
                notes: (workspaceNotes ?? []) as Note[] | undefined,
                musicxml,
                audioUrl,
                bpm: timeline.bpm,
                playheadTime: transport.position,
                onSeek: seek,
              })}
            </div>

          {footerControls && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                padding: "var(--s-2) var(--s-3)",
                borderTop: "1px solid var(--border)",
                background: "var(--panel-2)",
                fontSize: "var(--fs-xs)",
              }}
            >
              {footerControls}
            </div>
          )}
        </>
      )}
    </div>
  );
}
