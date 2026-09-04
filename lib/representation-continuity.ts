import type { RepresentationEntry } from "@/lib/stores/workspace";

type ConfirmedRepresentationVersions = {
  pianoRollVersionId?: string | null;
  scoreVersionId?: string | null;
};

/**
 * Preserve an already-hydrated symbolic view only across the short same-Work
 * rehydration gap where the freshly fetched bundle still confirms the exact
 * durable Version. The workspace store remains authoritative: omitted,
 * missing, or genuinely newer Versions are never carried forward here.
 */
export function retainRepresentationsConfirmedByVersion(
  previous: RepresentationEntry[],
  incoming: RepresentationEntry[],
  confirmed: ConfirmedRepresentationVersions,
): RepresentationEntry[] {
  const next = [...incoming];
  const candidates: Array<[RepresentationEntry["kind"], string | null | undefined]> = [
    ["piano_roll", confirmed.pianoRollVersionId],
    ["score", confirmed.scoreVersionId],
  ];

  for (const [kind, versionId] of candidates) {
    if (!versionId || next.some((representation) => representation.kind === kind)) continue;
    const existing = previous.find(
      (representation) => representation.kind === kind && representation.versionId === versionId,
    );
    if (existing) next.push(existing);
  }

  return next;
}
