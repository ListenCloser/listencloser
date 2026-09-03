import type { WorkArtifactBundle, WorkBundle } from "./domain.types";

export type ScoreArtifactEngine = "musescore" | "pm2s";

type ScoreArtifacts = {
  score: WorkArtifactBundle | undefined;
  renderedScore: WorkArtifactBundle | undefined;
  matchesPerformanceMidi: boolean;
};

function explicitScoreEngine(item: WorkArtifactBundle): ScoreArtifactEngine | null {
  const requested = item.latest_version?.metadata?.score_engine_requested;
  if (requested === "pm2s" || requested === "musescore") return requested;
  return null;
}

function requestedScoreEngine(item: WorkArtifactBundle): ScoreArtifactEngine {
  return explicitScoreEngine(item) ?? "musescore";
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

  let score = bundle.artifacts.find((item) => {
    if (item.artifact.kind !== "musicxml_score" || !item.latest_version || !item.signed_url) return false;
    if (requestedScoreEngine(item) !== scoreEngine) return false;
    if (!performanceMidiVersionId) return true;

    const notationVersionId = notationMidiVersionId(item);
    if (!notationVersionId) return false;
    // Historical score rows can point directly at canonical performance MIDI;
    // newer rows point at a notation-MIDI child. Both are exact lineage, so
    // retain compatibility without ever borrowing a tagged score from another source.
    if (notationVersionId === performanceMidiVersionId) return true;
    return versionsById.get(notationVersionId)?.parent_version_id === performanceMidiVersionId;
  });

  let legacyFallback = false;
  if (!score && scoreEngine === "musescore") {
    // Older persisted Works predate score-engine and notation-MIDI lineage
    // metadata. They were produced by the historical MuseScore baseline and
    // were already valid Score surfaces before score reinterpretation existed.
    // Preserve that display contract, but never borrow an explicitly tagged
    // score whose lineage does not match the canonical performance MIDI.
    score = bundle.artifacts.find((item) =>
      item.artifact.kind === "musicxml_score"
      && Boolean(item.latest_version)
      && Boolean(item.signed_url)
      && explicitScoreEngine(item) === null
      && item.latest_version?.metadata?.representation !== "score_source",
    );
    legacyFallback = Boolean(score);
  }

  const notationVersionId = notationMidiVersionId(score);
  let renderedScore = notationVersionId
    ? bundle.artifacts.find((item) => {
        if (item.artifact.kind !== "rendered_score" || !item.latest_version || !item.signed_url) return false;
        const metadataId = item.latest_version.metadata?.notation_midi_version_id;
        return item.latest_version.parent_version_id === notationVersionId || metadataId === notationVersionId;
      })
    : undefined;

  if (!renderedScore && legacyFallback) {
    // Legacy rendered-score rows likewise lack a pairing id. A Work-scoped
    // untagged MusicXML fallback may therefore use the historical single
    // rendered-score surface, matching the pre-reinterpretation behavior.
    renderedScore = bundle.artifacts.find((item) =>
      item.artifact.kind === "rendered_score" && Boolean(item.latest_version) && Boolean(item.signed_url),
    );
  }

  return {
    score,
    renderedScore,
    // Display compatibility and deterministic reuse are intentionally
    // different contracts. A pre-lineage score may stay visible, but it cannot
    // prove that it was built from the current canonical performance MIDI.
    matchesPerformanceMidi: Boolean(score && performanceMidiVersionId && !legacyFallback),
  };
}

export function hasReusableScoreArtifacts(
  bundle: WorkBundle,
  performanceMidiVersionId: string | null,
  scoreEngine: ScoreArtifactEngine,
): boolean {
  return selectScoreArtifacts(bundle, performanceMidiVersionId, scoreEngine).matchesPerformanceMidi;
}
