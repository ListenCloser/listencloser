/**
 * A shared workspace is allowed to publish an async load only when that load
 * is both the newest request and still targets the Work the user selected.
 */
export function canPublishWorkLoad({
  workId,
  activeWorkId,
  sequence,
  latestSequence,
}: {
  workId: string;
  activeWorkId: string | null;
  sequence: number;
  latestSequence: number;
}): boolean {
  return workId === activeWorkId && sequence === latestSequence;
}
