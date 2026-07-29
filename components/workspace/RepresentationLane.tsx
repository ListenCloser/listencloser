"use client";

import type { ReactNode } from "react";
import type { RepresentationKind } from "@/lib/stores/workspace";
import { renderRepresentation } from "@/lib/representation-registry";
import { useTransport } from "@/lib/stores/transport";

type Note = { pitch: number; start: number; end: number; velocity: number };

type RepresentationLaneProps = {
  kind: RepresentationKind;
  label: string;
  sourceLabel: string;
  confidence: number | null;
  isExpanded: boolean;
  isFocused: boolean;
  onExpand: () => void;
  onFocus: () => void;
  onRemove: () => void;
  children?: ReactNode;
  footerControls?: ReactNode;
  editable?: boolean;
  correctedNotes?: Note[] | null;
  onNotesChange?: ((notes: Note[]) => void) | undefined;
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
  isFocused,
  onExpand,
  onFocus,
  onRemove,
  children,
  footerControls,
  editable,
  correctedNotes,
  onNotesChange,
}: RepresentationLaneProps) {
  const { transport } = useTransport();
  const glyph = KIND_GLYPHS[kind] ?? "▯";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        border: `1px solid ${isFocused ? "var(--accent)" : "var(--border)"}`,
        borderRadius: "var(--r-md)",
        background: "var(--panel)",
        overflow: "hidden",
        boxShadow: isFocused ? "0 0 16px rgba(192,132,252,0.15)" : undefined,
        transition: "box-shadow var(--dur) var(--ease)",
        ...(isExpanded ? { flex: 1 } : { flexShrink: 0 }),
      }}
    >
      <div
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

        <button
          className="icon-btn ghost"
          onClick={(e) => {
            e.stopPropagation();
            onFocus();
          }}
          style={{
            fontSize: "var(--fs-xs)",
            padding: "2px 8px",
            marginLeft: "auto",
            background: isFocused ? "var(--accent-soft)" : undefined,
            color: isFocused ? "var(--accent)" : undefined,
          }}
          title="Focus this representation"
        >
          ⊙
        </button>

        <button
          className="icon-btn ghost danger"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          style={{ fontSize: "var(--fs-xs)", padding: "2px 8px" }}
          title="Remove"
        >
          ✕
        </button>
      </div>

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
                notes: (correctedNotes ?? []) as Note[] | undefined,
                bpm: 120,
                playheadTime: transport.position,
                editable: editable ?? false,
                onNotesChange: onNotesChange as ((notes: Note[]) => void) | undefined,
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
