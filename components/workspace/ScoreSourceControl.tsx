"use client";

import Button from "@/components/ui/Button";
import SelectField from "@/components/ui/SelectField";
import type { ScoreDisplaySelection, ScoreSourceOption } from "@/lib/score-sources";
import styles from "./ScoreSourceControl.module.css";

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
    <div aria-label="Score controls" className={styles.root}>
      <label className={styles.field}>
        <span>Score source</span>
        <SelectField
          aria-label="Score source"
          value={selectionValue(selection)}
          disabled={disabled}
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
        </SelectField>
      </label>
      <Button fullWidth disabled={attachDisabled} onClick={onAttach}>Attach score</Button>
    </div>
  );
}
