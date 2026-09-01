from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1))


# API client: score-only workflow uses the same mutation/cache invalidation seam.
replace_once(
    "lib/api-client.ts",
    '''export async function startVariationWorkflow(
''',
    '''export async function startScoreWorkflow(
  performanceMidiVersionId: string,
  projectId: string,
  scoreEngine?: ScoreEngine,
): Promise<{ workflow: Workflow; job: Job }> {
  return mutateVersionWorks([performanceMidiVersionId], async () => {
    const result = await openapiClient.POST("/api/v1/workflows/score", {
      body: {
        performance_midi_version_id: performanceMidiVersionId,
        project_id: projectId,
        ...(scoreEngine ? { score_engine: scoreEngine } : {}),
      },
    });
    return normalizeWorkflowJob(requireOpenApiData(result));
  });
}

export async function startVariationWorkflow(
''',
)

# Workspace: distinguish preference changes from an explicit loaded-work rebuild request.
replace_once(
    "lib/stores/workspace.tsx",
    '''  scoreEngine: ScoreEngine;
  analysisState: AnalysisState;
''',
    '''  scoreEngine: ScoreEngine;
  scoreEngineAction: { id: number; engine: ScoreEngine } | null;
  analysisState: AnalysisState;
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''  setScoreEngine: (engine: ScoreEngine) => void;
  setAnalysisState: (state: AnalysisState) => void;
''',
    '''  setScoreEngine: (engine: ScoreEngine) => void;
  requestScoreEngine: (engine: ScoreEngine) => void;
  setAnalysisState: (state: AnalysisState) => void;
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''    scoreEngine: "musescore",
    analysisState: "idle",
''',
    '''    scoreEngine: "musescore",
    scoreEngineAction: null,
    analysisState: "idle",
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);
''',
    '''  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);
  const requestScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => ({
    ...prev,
    scoreEngine,
    scoreEngineAction: {
      id: (prev.scoreEngineAction?.id ?? 0) + 1,
      engine: scoreEngine,
    },
  })), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''      setTranscriptionProfile,
      setScoreEngine,
      setAnalysisState,
''',
    '''      setTranscriptionProfile,
      setScoreEngine,
      requestScoreEngine,
      setAnalysisState,
''',
)

# Selector: loaded recordings issue an explicit reinterpretation action; empty desk only sets preference.
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '''function ScoreEngineToggle() {
  const { workspace, setScoreEngine } = useWorkspace();
''',
    '''function ScoreEngineToggle({ loaded = false }: { loaded?: boolean }) {
  const { workspace, requestScoreEngine, setScoreEngine } = useWorkspace();
''',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '''            onClick={() => setScoreEngine(option.id)}
''',
    '''            onClick={() => loaded ? requestScoreEngine(option.id) : setScoreEngine(option.id)}
''',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '''        {preparingRepresentations && (
          <span
            className="muted"
            role="status"
            style={{ alignSelf: "center", fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}
          >
            Preparing representations…
          </span>
        )}
      </div>
''',
    '''        {preparingRepresentations && (
          <span
            className="muted"
            role="status"
            style={{ alignSelf: "center", fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}
          >
            Preparing representations…
          </span>
        )}
        {activeView === "score" && (
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
            <span className="muted" style={{ fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}>
              Score interpretation
            </span>
            <ScoreEngineToggle loaded />
          </div>
        )}
      </div>
''',
)

# WorkspaceSession: select score artifacts by engine + notation identity and run score-only work on explicit cache misses.
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''  startCompareWorkflow,
  startUnderstandWorkflow,
  startVariationWorkflow,
''',
    '''  startCompareWorkflow,
  startScoreWorkflow,
  startUnderstandWorkflow,
  startVariationWorkflow,
''',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''import { buildPlaybackSources } from "@/lib/playback-sources";
''',
    '''import { buildPlaybackSources } from "@/lib/playback-sources";
import { performanceMidiVersionId, selectScoreArtifacts } from "@/lib/score-artifacts";
''',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''  const loadedWorkRef = useRef<string | null>(null);
  const initializedProjectSelectionRef = useRef<string | null>(null);
''',
    '''  const loadedWorkRef = useRef<string | null>(null);
  const loadedBundleRef = useRef<Awaited<ReturnType<typeof getWorkBundle>> | null>(null);
  const initializedProjectSelectionRef = useRef<string | null>(null);
''',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''      const bundle = await getWorkBundle(workId);
      if (sequence !== loadSequenceRef.current) return;

      const latestJob = bundle.jobs[0];
''',
    '''      const bundle = await getWorkBundle(workId);
      if (sequence !== loadSequenceRef.current) return;
      loadedBundleRef.current = bundle;

      const latestJob = bundle.jobs[0];
''',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''      const score = latestByKind.get("musicxml_score");
      const renderedScore = latestByKind.get("rendered_score");
''',
    '''      const { score, renderedScore } = selectScoreArtifacts(bundle.artifacts, scoreEngine);
''',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''  }, [clearProcessingRefresh, queryClient, replaceRepresentations, replaceSources, resetTimeline, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);
''',
    '''  }, [clearProcessingRefresh, queryClient, replaceRepresentations, replaceSources, resetTimeline, scoreEngine, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);
''',
)

score_effect_anchor = '''  const handledStudioAction = useRef(0);
  useEffect(() => {
'''
score_effect = '''  const handledScoreEngineAction = useRef(0);
  useEffect(() => {
    const action = workspace.scoreEngineAction;
    const workId = workspace.activeWorkId;
    if (!action || action.id === handledScoreEngineAction.current || !projectId || !workId) return;
    handledScoreEngineAction.current = action.id;

    const bundle = loadedBundleRef.current?.work.id === workId ? loadedBundleRef.current : null;
    if (bundle && selectScoreArtifacts(bundle.artifacts, action.engine).score) {
      // `scoreEngine` is already updated by the request action. The loadWork
      // dependency refreshes the selected representation from the cached bundle.
      return;
    }

    const performanceVersionId = bundle ? performanceMidiVersionId(bundle.artifacts) : null;
    if (!performanceVersionId) {
      setError("Score reinterpretation requires the canonical performance transcription.");
      setStage("error");
      return;
    }

    void (async () => {
      setProcessingWorkId(workId);
      setStage("processing");
      setProgress(0);
      setError(null);
      setMessage(`Rebuilding Score with ${action.engine === "pm2s" ? "PM2S" : "MuseScore"}…`);
      try {
        const { job } = await startScoreWorkflow(performanceVersionId, projectId, action.engine);
        setActiveJobId(job.id);
        await waitForJob(job.id, (current) => {
          setMessage(current.message || "Rebuilding Score…");
          setProgress(Math.round(current.progress * 100));
        });
        await loadWork(workId);
      } catch (cause) {
        const disconnected = cause instanceof JobObservationError;
        setError(cause instanceof Error ? cause.message : "Could not rebuild Score");
        setStage(disconnected ? "disconnected" : "error");
      }
    })();
  }, [loadWork, projectId, workspace.activeWorkId, workspace.scoreEngineAction]);

  const handledStudioAction = useRef(0);
  useEffect(() => {
'''
replace_once("components/workspace/WorkspaceSession.tsx", score_effect_anchor, score_effect)
