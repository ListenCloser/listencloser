"use client";

import type { ScoreDisplaySelection, ScoreSourceOption } from "@/lib/score-sources";

function selectionValue(selection: ScoreDisplaySelection): string {
  if (!selection) return "";
  return selection.kind === "engine"
    ? `engine:${selection.engine}`
    : `source:${selection.versionId}`;
}

export default function ScoreSourceControl({
  selection,
  sources,
  disabled = false,
  attachDisabled = disabled,
  onSelectEngine,
  onSelectSource,
  onAttach,
}: {
  selection: ScoreDisplaySelection;
  sources: readonly ScoreSourceOption[];
  disabled?: boolean;
  attachDisabled?: boolean;
  onSelectEngine: (engine: "musescore" | "pm2s") => void;
  onSelectSource: (versionId: string) => void;
  onAttach: () => void;
}) {
  return (
    <div aria-label="Score controls" style={{ display: "grid", gap: "6px" }}>
      <label className="muted" style={{ display: "grid", gap: "4px", fontSize: "var(--fs-xs)" }}>
        <span>Choose what the Score view shows</span>
        <select
          aria-label="Score source"
          value={selectionValue(selection)}
          disabled={disabled}
          style={{ width: "100%" }}
          onChange={(event) => {
            const value = event.target.value;
            if (value === "engine:musescore") onSelectEngine("musescore");
            else if (value === "engine:pm2s") onSelectEngine("pm2s");
            else if (value.startsWith("source:")) onSelectSource(value.slice("source:".length));
          }}
        >
          {!selection && <option value="">Choose score</option>}
          {sources.length > 0 && (
            <optgroup label="Attached scores">
              {sources.map((source) => (
                <option key={source.versionId} value={`source:${source.versionId}`}>
                  {source.label}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label="Generated interpretations">
            <option value="engine:musescore">MuseScore</option>
            <option value="engine:pm2s">PM2S · MuseScore import</option>
          </optgroup>
        </select>
      </label>
      <button type="button" className="btn btn-sm" disabled={attachDisabled} onClick={onAttach}>
        Attach score
      </button>
    </div>
  );
}
