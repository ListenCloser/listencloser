"use client";

import { useEffect, useRef, useState } from "react";
import { clearWorkDataCache, getInsights } from "@/lib/api-client";
import type { Insight } from "@/lib/domain.types";
import { waitForJob } from "@/lib/job-tracking";
import {
  startChordMiniInterpretation,
  type HarmonyInterpretationEngine,
} from "@/lib/relation-api-client";
import { useWorkspace } from "@/lib/stores/workspace";

const HARMONY_KINDS = new Set(["chord", "roman_numeral", "harmonic_function"]);

function insightEngine(insight: Insight): string | null {
  const engine = insight.provenance?.engine;
  return typeof engine === "string" ? engine : null;
}

function hasChordEngine(insights: Insight[], engine: HarmonyInterpretationEngine): boolean {
  return insights.some(
    (insight) => insight.kind === "chord" && insightEngine(insight) === engine,
  );
}

export function selectHarmonyInterpretation(
  insights: Insight[],
  engine: HarmonyInterpretationEngine,
): Insight[] {
  return insights.filter((insight) => {
    if (!HARMONY_KINDS.has(insight.kind)) return true;
    if (insight.kind === "chord") return insightEngine(insight) === engine;
    return engine === "lv-chordia";
  });
}

function initialEngine(insights: Insight[]): HarmonyInterpretationEngine {
  return hasChordEngine(insights, "chordmini") && !hasChordEngine(insights, "lv-chordia")
    ? "chordmini"
    : "lv-chordia";
}

export default function HarmonyInterpretationControl() {
  const { workspace, setInsights } = useWorkspace();
  const activeWorkId = workspace.activeWorkId;
  const midiVersionId = workspace.representations.find(
    (item) => item.kind === "piano_roll",
  )?.versionId;
  const audioVersionId = workspace.representations.find(
    (item) => item.kind === "waveform",
  )?.versionId;
  const [engine, setEngine] = useState<HarmonyInterpretationEngine>(() =>
    initialEngine(workspace.insights),
  );
  const [hasLvChordia, setHasLvChordia] = useState(() =>
    hasChordEngine(workspace.insights, "lv-chordia"),
  );
  const [hasChordMini, setHasChordMini] = useState(() =>
    hasChordEngine(workspace.insights, "chordmini"),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filteredOnce = useRef(false);

  useEffect(() => {
    if (filteredOnce.current) return;
    const lvAvailable = hasChordEngine(workspace.insights, "lv-chordia");
    const chordMiniAvailable = hasChordEngine(workspace.insights, "chordmini");
    setHasLvChordia(lvAvailable);
    setHasChordMini(chordMiniAvailable);
    if (!lvAvailable || !chordMiniAvailable) return;

    filteredOnce.current = true;
    setInsights(selectHarmonyInterpretation(workspace.insights, engine));
  }, [engine, setInsights, workspace.insights]);

  if (
    !activeWorkId
    || !midiVersionId
    || !audioVersionId
    || (!hasLvChordia && !hasChordMini)
  ) {
    return null;
  }

  const refreshFor = async (nextEngine: HarmonyInterpretationEngine) => {
    clearWorkDataCache();
    const allInsights = await getInsights(midiVersionId);
    setHasLvChordia(hasChordEngine(allInsights, "lv-chordia"));
    setHasChordMini(hasChordEngine(allInsights, "chordmini"));
    setInsights(selectHarmonyInterpretation(allInsights, nextEngine));
    setEngine(nextEngine);
  };

  const choose = async (nextEngine: HarmonyInterpretationEngine) => {
    if (busy || nextEngine === engine) return;
    setBusy(true);
    setError(null);
    try {
      if (nextEngine === "chordmini" && !hasChordMini) {
        const result = await startChordMiniInterpretation(
          activeWorkId,
          midiVersionId,
          audioVersionId,
        );
        const jobId = result.job.id;
        if (!jobId) {
          throw new Error("ChordMini interpretation did not return a job id");
        }
        await waitForJob(jobId, () => undefined);
      }
      await refreshFor(nextEngine);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not change Harmony interpretation");
    } finally {
      setBusy(false);
    }
  };

  const currentLabel = engine === "chordmini" ? "ChordMini · Experimental" : "lv-chordia";

  return (
    <details
      style={{
        margin: "0 0 var(--s-2)",
        borderBottom: "1px solid var(--border-subtle)",
        paddingBottom: "var(--s-2)",
      }}
    >
      <summary
        style={{ cursor: "pointer", fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}
      >
        Harmony · {currentLabel}
      </summary>
      <div
        style={{
          display: "flex",
          gap: "var(--s-2)",
          alignItems: "center",
          flexWrap: "wrap",
          paddingTop: "var(--s-2)",
        }}
      >
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Try another interpretation
        </span>
        <button
          type="button"
          className="btn"
          disabled={busy || engine === "lv-chordia" || !hasLvChordia}
          onClick={() => void choose("lv-chordia")}
        >
          lv-chordia
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy || engine === "chordmini"}
          onClick={() => void choose("chordmini")}
        >
          {busy && engine !== "chordmini" ? "Generating…" : "ChordMini · Experimental"}
        </button>
        {error && <span role="alert" style={{ fontSize: "var(--fs-xs)" }}>{error}</span>}
      </div>
    </details>
  );
}