import type { WorkArtifactBundle } from "@/lib/domain.types";
import type { ScoreEngine } from "@/lib/stores/workspace";

type SelectedScoreArtifacts = {
  score: WorkArtifactBundle | null;
  renderedScore: WorkArtifactBundle | null;
};

function scoreEngineForArtifact(item: WorkArtifactBundle): ScoreEngine | null {
  if (item.artifact.kind !== "musicxml_score" || !item.latest_version) return null;
  const requested = item.latest_version.metadata?.score_engine_requested;
  if (requested === "pm2s") return "pm2s";
  if (requested === "musescore") return "musescore";
  // Scores created before explicit routing are the historical MuseScore path.
  return "musescore";
}

export function selectScoreArtifacts(
  artifacts: WorkArtifactBundle[],
  engine: ScoreEngine,
): SelectedScoreArtifacts {
  const score = artifacts.find(
    (item) => Boolean(item.latest_version && item.signed_url) && scoreEngineForArtifact(item) === engine,
  ) ?? null;
  if (!score?.latest_version) return { score: null, renderedScore: null };

  const notationMidiVersionId = score.latest_version.metadata?.notation_midi_version_id;
  const renderedScore = typeof notationMidiVersionId === "string"
    ? artifacts.find((item) => (
      item.artifact.kind === "rendered_score"
      && Boolean(item.latest_version && item.signed_url)
      && item.latest_version?.metadata?.notation_midi_version_id === notationMidiVersionId
    )) ?? null
    : null;

  return { score, renderedScore };
}

export function performanceMidiVersionId(artifacts: WorkArtifactBundle[]): string | null {
  const performance = artifacts.find(
    (item) => item.artifact.kind === "midi_performance" && item.latest_version,
  );
  return performance?.latest_version?.id ?? null;
}
