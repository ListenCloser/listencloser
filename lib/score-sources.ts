import type { WorkArtifactBundle, WorkBundle } from "./domain.types";

export type ScoreDisplaySelection =
  | { kind: "engine"; engine: "musescore" | "pm2s" }
  | { kind: "source"; versionId: string }
  | null;

export type ScoreSourceOption = {
  versionId: string;
  label: string;
};

function isScoreSource(item: WorkArtifactBundle): boolean {
  return item.artifact.kind === "musicxml_score"
    && Boolean(item.latest_version)
    && Boolean(item.signed_url)
    && item.latest_version?.metadata?.representation === "score_source";
}

function sourceFilename(item: WorkArtifactBundle): string {
  const originalFilename = item.latest_version?.metadata?.original_filename;
  if (typeof originalFilename === "string" && originalFilename.trim()) {
    return originalFilename.trim();
  }
  const label = item.latest_version?.label?.trim();
  return label || "Attached score";
}

export function scoreSourceOptions(bundle: WorkBundle): ScoreSourceOption[] {
  const sources = bundle.artifacts
    .filter(isScoreSource)
    .map((item) => ({
      versionId: item.latest_version!.id,
      filename: sourceFilename(item),
    }))
    // Ordering is presentation-only. Never use recency to grant source authority.
    .sort((left, right) => left.filename.localeCompare(right.filename)
      || left.versionId.localeCompare(right.versionId));

  const totals = new Map<string, number>();
  for (const source of sources) totals.set(source.filename, (totals.get(source.filename) ?? 0) + 1);
  const seen = new Map<string, number>();

  return sources.map((source) => {
    const ordinal = (seen.get(source.filename) ?? 0) + 1;
    seen.set(source.filename, ordinal);
    const duplicate = (totals.get(source.filename) ?? 0) > 1;
    return {
      versionId: source.versionId,
      label: duplicate
        ? `Attached · ${source.filename} (${ordinal})`
        : `Attached · ${source.filename}`,
    };
  });
}

export function defaultScoreSourceVersionId(options: readonly ScoreSourceOption[]): string | null {
  // One source is unambiguous. Two or more sources must be chosen explicitly;
  // there is deliberately no "latest attached score wins" fallback.
  return options.length === 1 ? options[0].versionId : null;
}

export function selectScoreSource(
  bundle: WorkBundle,
  versionId: string | null,
): WorkArtifactBundle | undefined {
  if (!versionId) return undefined;
  return bundle.artifacts.find((item) =>
    isScoreSource(item) && item.latest_version?.id === versionId,
  );
}
