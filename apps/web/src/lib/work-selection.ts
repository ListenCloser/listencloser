export type SelectableWork = { id: string };

export function successorAfterDelete<T extends SelectableWork>(works: T[], deletingId: string): T | null {
  const deletingIndex = works.findIndex((work) => work.id === deletingId);
  if (deletingIndex < 0) return null;
  return works[deletingIndex + 1] ?? works[deletingIndex - 1] ?? null;
}
