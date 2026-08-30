type ScoreRendererModule = typeof import("opensheetmusicdisplay");

let scoreRendererModulePromise: Promise<ScoreRendererModule> | null = null;

/**
 * Load the Score renderer through one shared promise.
 *
 * Intent warming and the actual SheetMusic mount must converge on the same
 * dynamic import so preloading never creates a second renderer/cache path.
 * A failed import is cleared so the selected Score can retry normally.
 */
export function loadScoreRenderer(): Promise<ScoreRendererModule> {
  if (!scoreRendererModulePromise) {
    scoreRendererModulePromise = import("opensheetmusicdisplay").catch((error) => {
      scoreRendererModulePromise = null;
      throw error;
    });
  }
  return scoreRendererModulePromise;
}

/** Start the shared dynamic import without surfacing speculative-load errors. */
export function preloadScoreRenderer(): void {
  void loadScoreRenderer().catch(() => undefined);
}
