/**
 * Warm the existing lazy Score chunk on deliberate user intent.
 *
 * The browser module loader owns fetch/evaluation de-duplication. SheetMusic
 * keeps its normal dynamic import, which will resolve from that native module
 * cache if this warmup completes first. No parallel application cache is
 * introduced here.
 */
export function preloadScoreRenderer(): void {
  void import("opensheetmusicdisplay").catch(() => undefined);
}
