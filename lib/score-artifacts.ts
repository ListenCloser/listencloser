import type { WorkArtifactBundle, WorkBundle } from "./domain.types";

export type ScoreArtifactEngine = "musescore" | "pm2s";

type ScoreArtifacts = {
  score: WorkArtifactBundle | undefined;
  renderedScore: WorkArtifactBundle | undefined;
};

function requestedScoreEngine(item: WorkArtifactBundle): ScoreArtifactEngine {
  return item.latest_version?.metadata?.score_engine_requested === "pm2s" ? "pm2s" : "musescore";
}

function notationMidiVersionId(item: WorkArtifactBundle | undefined): string | null {
  if (!item?.latest_version) return null;
  const metadataId = item.latest_version.metadata?.notation_midi_version_id;
  if (typeof metadataId === "string" && metadataId) return metadataId;
  return item.latest_version.parent_version_id;
}

export function selectScoreArtifacts(
  bundle: WorkBundle,
  performanceMidiVersionId: string | null,
  scoreEngine: ScoreArtifactEngine,
): ScoreArtifacts {
  const versionsById = new Map(
    bundle.artifacts.flatMap((item) => item.latest_version ? [[item.latest_version.id, item.latest_version] as const] : []),
  );

  const score = bundle.artifacts.find((item) => {
    if (item.artifact.kind !== "musicxml_score" || !item.latest_version || !item.signed_url) return false;
    if (requestedScoreEngine(item) !== scoreEngine) return false;
    if (!performanceMidiVersionId) return true;

    const notationVersionId = notationMidiVersionId(item);
    if (!notationVersionId) return false;
    // Historical score rows can point directly at canonical performance MIDI;
    // newer rows point at a notation-MIDI child. Both are exact lineage, so
    // retain compatibility without ever borrowing a score from another source.
    if (notationVersionId === performanceMidiVersionId) return true;
    return versionsById.get(notationVersionId)?.parent_version_id === performanceMidiVersionId;
  });

  const notationVersionId = notationMidiVersionId(score);
  const renderedScore = notationVersionId
    ? bundle.artifacts.find((item) => {
        if (item.artifact.kind !== "rendered_score" || !item.latest_version || !item.signed_url) return false;
        const metadataId = item.latest_version.metadata?.notation_midi_version_id;
        return item.latest_version.parent_version_id === notationVersionId || metadataId === notationVersionId;
      })
    : undefined;

  return { score, renderedScore };
}
