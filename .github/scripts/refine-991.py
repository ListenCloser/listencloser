from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"expected patch marker not found in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


# Workspace state: a loaded-work engine request is both selection and, when needed,
# a deliberate score-only rebuild action. Pre-import selection remains plain state.
replace_once(
    "lib/stores/workspace.tsx",
    '  scoreEngine: ScoreEngine;\n  scoreRebuildRequestId: number;\n  analysisState: AnalysisState;',
    '  scoreEngine: ScoreEngine;\n  scoreEngineAction: { id: number; engine: ScoreEngine } | null;\n  analysisState: AnalysisState;',
)
replace_once(
    "lib/stores/workspace.tsx",
    '  setScoreEngine: (engine: ScoreEngine) => void;\n  requestScoreRebuild: () => void;\n  setAnalysisState: (state: AnalysisState) => void;',
    '  setScoreEngine: (engine: ScoreEngine) => void;\n  requestScoreEngine: (engine: ScoreEngine) => void;\n  setAnalysisState: (state: AnalysisState) => void;',
)
replace_once(
    "lib/stores/workspace.tsx",
    '    scoreEngine: "musescore",\n    scoreRebuildRequestId: 0,\n    analysisState: "idle",',
    '    scoreEngine: "musescore",\n    scoreEngineAction: null,\n    analysisState: "idle",',
)
replace_once(
    "lib/stores/workspace.tsx",
    '  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);\n  const requestScoreRebuild = useCallback(() => setWorkspace((prev) => ({ ...prev, scoreRebuildRequestId: prev.scoreRebuildRequestId + 1 })), []);\n  const setAnalysisState',
    '''  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);\n  const requestScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => ({\n    ...prev,\n    scoreEngine,\n    scoreEngineAction: {\n      id: (prev.scoreEngineAction?.id ?? 0) + 1,\n      engine: scoreEngine,\n    },\n  })), []);\n  const setAnalysisState''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '      setScoreEngine,\n      requestScoreRebuild,\n      setAnalysisState,',
    '      setScoreEngine,\n      requestScoreEngine,\n      setAnalysisState,',
)

# Keep a full Work bundle snapshot so selection can distinguish a cache hit from an
# uncached engine request without creating duplicate deterministic outputs.
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '  const loadedWorkRef = useRef<string | null>(null);\n  const initializedProjectSelectionRef',
    '  const loadedWorkRef = useRef<string | null>(null);\n  const loadedBundleRef = useRef<Awaited<ReturnType<typeof getWorkBundle>> | null>(null);\n  const initializedProjectSelectionRef',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '      const bundle = await getWorkBundle(workId);\n      if (sequence !== loadSequenceRef.current) return;\n\n      const latestJob',
    '      const bundle = await getWorkBundle(workId);\n      if (sequence !== loadSequenceRef.current) return;\n      loadedBundleRef.current = bundle;\n\n      const latestJob',
)
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '  const handledScoreRebuildRequest = useRef(workspace.scoreRebuildRequestId);\n  const handledStudioAction',
    '  const handledScoreEngineAction = useRef(0);\n  const handledStudioAction',
)
old_effect = '''  useEffect(() => {\n    const requestId = workspace.scoreRebuildRequestId;\n    if (!requestId || requestId === handledScoreRebuildRequest.current || !projectId || !workspace.activeWorkId) return;\n    handledScoreRebuildRequest.current = requestId;\n\n    const workId = workspace.activeWorkId;\n    const performanceMidiVersionId = performanceMidiVersionRef.current;\n    if (!performanceMidiVersionId) {\n      setError("A canonical performance MIDI is required before rebuilding Score.");\n      setStage("error");\n      return;\n    }\n\n    void (async () => {\n      setError(null);\n      setProgress(0);\n      setProcessingWorkId(workId);\n      setStage("processing");\n      setMessage(`Rebuilding Score with ${scoreEngine === "pm2s" ? "PM2S" : "MuseScore"}…`);\n      try {\n        const { job } = await startScoreWorkflow(performanceMidiVersionId, projectId, scoreEngine);\n        setActiveJobId(job.id);\n        await loadWork(workId);\n      } catch (cause) {\n        setActiveJobId(null);\n        setError(cause instanceof Error ? cause.message : "Could not rebuild Score");\n        setStage("error");\n      }\n    })();\n  }, [loadWork, projectId, scoreEngine, workspace.activeWorkId, workspace.scoreRebuildRequestId]);\n'''
new_effect = '''  useEffect(() => {\n    const action = workspace.scoreEngineAction;\n    const workId = workspace.activeWorkId;\n    if (!action || action.id === handledScoreEngineAction.current || !projectId || !workId) return;\n    handledScoreEngineAction.current = action.id;\n\n    const bundle = loadedBundleRef.current?.work.id === workId ? loadedBundleRef.current : null;\n    const performanceMidiVersionId = performanceMidiVersionRef.current;\n    if (bundle && selectScoreArtifacts(bundle, performanceMidiVersionId, action.engine).score) {\n      // The selected engine already exists for this exact canonical performance\n      // MIDI. Updating scoreEngine changes loadWork identity, so the normal Work\n      // refresh switches Score + score playback without a compute/storage write.\n      return;\n    }\n\n    if (!performanceMidiVersionId) {\n      setError("Score reinterpretation requires the canonical performance transcription.");\n      setStage("error");\n      return;\n    }\n\n    void (async () => {\n      setError(null);\n      setProgress(0);\n      setProcessingWorkId(workId);\n      setStage("processing");\n      setMessage(`Rebuilding Score with ${action.engine === "pm2s" ? "PM2S" : "MuseScore"}…`);\n      try {\n        const { job } = await startScoreWorkflow(performanceMidiVersionId, projectId, action.engine);\n        setActiveJobId(job.id);\n        await waitForJob(job.id, (current) => {\n          setMessage(current.message || "Rebuilding Score…");\n          setProgress(Math.round(current.progress * 100));\n        });\n        await loadWork(workId);\n      } catch (cause) {\n        setActiveJobId(null);\n        const disconnected = cause instanceof JobObservationError;\n        setError(cause instanceof Error ? cause.message : "Could not rebuild Score");\n        setStage(disconnected ? "disconnected" : "error");\n      }\n    })();\n  }, [loadWork, projectId, workspace.activeWorkId, workspace.scoreEngineAction]);\n'''
replace_once("components/workspace/WorkspaceSession.tsx", old_effect, new_effect)

# Existing Work control: scope interpretation routing to the Score view. Clicking an
# engine is the deliberate reinterpretation action. Empty-workspace processing
# settings remain a plain pre-import preference.
replace_once(
    "components/workspace/RepresentationStack.tsx",
    'function ScoreEngineToggle() {\n  const { workspace, setScoreEngine } = useWorkspace();',
    'function ScoreEngineToggle({ loaded = false }: { loaded?: boolean }) {\n  const { workspace, requestScoreEngine, setScoreEngine } = useWorkspace();',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '            onClick={() => setScoreEngine(option.id)}',
    '            onClick={() => loaded ? requestScoreEngine(option.id) : setScoreEngine(option.id)}',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '  const { workspace, requestImport, requestScoreRebuild, setActiveRepresentation, clearSelection } = useWorkspace();',
    '  const { workspace, requestImport, setActiveRepresentation, clearSelection } = useWorkspace();',
)
old_toolbar = '''        <div\n          aria-label="Score controls"\n          style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-2)" }}\n        >\n          <span className="muted" style={{ fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}>Score</span>\n          <ScoreEngineToggle />\n          <button type="button" className="btn" onClick={requestScoreRebuild}>Rebuild Score</button>\n        </div>'''
new_toolbar = '''        {activeView === "score" && (\n          <div\n            aria-label="Score controls"\n            style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-2)" }}\n          >\n            <span className="muted" style={{ fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}>Score interpretation</span>\n            <ScoreEngineToggle loaded />\n          </div>\n        )}'''
replace_once("components/workspace/RepresentationStack.tsx", old_toolbar, new_toolbar)
