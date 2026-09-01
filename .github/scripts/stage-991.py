from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"expected patch marker not found in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


Path("lib/score-artifacts.ts").write_text('''import type { WorkArtifactBundle, WorkBundle } from "./domain.types";

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
''')

Path("lib/score-artifacts.test.ts").write_text('''import { describe, expect, it } from "vitest";
import type { WorkBundle } from "./domain.types";
import { selectScoreArtifacts } from "./score-artifacts";

function bundle(): WorkBundle {
  const artifact = (id: string, kind: string, versionId: string, parentVersionId: string | null, metadata: Record<string, unknown> = {}) => ({
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: parentVersionId,
      metadata,
    },
    versions: [],
    signed_url: `https://example.test/${versionId}`,
  });

  return {
    work: { id: "work" },
    jobs: [],
    artifacts: [
      artifact("perf-artifact", "midi_performance", "perf-v1", null),
      artifact("legacy-perf-artifact", "midi_performance", "perf-old", null),
      artifact("muse-notation", "midi_corrected", "muse-notation-v1", "perf-v1", { score_engine_requested: "musescore" }),
      artifact("muse-score", "musicxml_score", "muse-score-v1", "muse-notation-v1", { notation_midi_version_id: "muse-notation-v1" }),
      artifact("muse-audio", "rendered_score", "muse-audio-v1", "muse-notation-v1", { notation_midi_version_id: "muse-notation-v1" }),
      artifact("pm2s-notation", "midi_corrected", "pm2s-notation-v1", "perf-v1", { score_engine_requested: "pm2s" }),
      artifact("pm2s-score", "musicxml_score", "pm2s-score-v1", "pm2s-notation-v1", { score_engine_requested: "pm2s", notation_midi_version_id: "pm2s-notation-v1" }),
      artifact("pm2s-audio", "rendered_score", "pm2s-audio-v1", "pm2s-notation-v1", { notation_midi_version_id: "pm2s-notation-v1" }),
      artifact("old-pm2s-notation", "midi_corrected", "old-pm2s-notation-v1", "perf-old", { score_engine_requested: "pm2s" }),
      artifact("old-pm2s-score", "musicxml_score", "old-pm2s-score-v1", "old-pm2s-notation-v1", { score_engine_requested: "pm2s", notation_midi_version_id: "old-pm2s-notation-v1" }),
    ],
  } as unknown as WorkBundle;
}

describe("selectScoreArtifacts", () => {
  it("selects the requested score engine and its matching playback", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "pm2s");
    expect(selected.score?.latest_version?.id).toBe("pm2s-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("pm2s-audio-v1");
  });

  it("treats legacy score output without engine metadata as MuseScore", () => {
    const selected = selectScoreArtifacts(bundle(), "perf-v1", "musescore");
    expect(selected.score?.latest_version?.id).toBe("muse-score-v1");
    expect(selected.renderedScore?.latest_version?.id).toBe("muse-audio-v1");
  });

  it("does not select a result derived from a different performance MIDI", () => {
    const selected = selectScoreArtifacts(bundle(), "missing-performance", "pm2s");
    expect(selected.score).toBeUndefined();
    expect(selected.renderedScore).toBeUndefined();
  });
});
''')

replace_once(
    "lib/api-client.ts",
    "\nexport async function startVariationWorkflow(\n",
    '''\nexport async function startScoreWorkflow(\n  performanceMidiVersionId: string,\n  projectId: string,\n  scoreEngine: ScoreEngine,\n): Promise<{ workflow: Workflow; job: Job }> {\n  return mutateVersionWorks([performanceMidiVersionId], async () => {\n    const result = await openapiClient.POST("/api/v1/workflows/score", {\n      body: {\n        performance_midi_version_id: performanceMidiVersionId,\n        project_id: projectId,\n        score_engine: scoreEngine,\n      },\n    });\n    return normalizeWorkflowJob(requireOpenApiData(result));\n  });\n}\n\nexport async function startVariationWorkflow(\n''',
)

replace_once("lib/stores/workspace.tsx", "  scoreEngine: ScoreEngine;\n  analysisState: AnalysisState;", "  scoreEngine: ScoreEngine;\n  scoreRebuildRequestId: number;\n  analysisState: AnalysisState;")
replace_once("lib/stores/workspace.tsx", "  setScoreEngine: (engine: ScoreEngine) => void;\n  setAnalysisState: (state: AnalysisState) => void;", "  setScoreEngine: (engine: ScoreEngine) => void;\n  requestScoreRebuild: () => void;\n  setAnalysisState: (state: AnalysisState) => void;")
replace_once("lib/stores/workspace.tsx", "    scoreEngine: \"musescore\",\n    analysisState: \"idle\",", "    scoreEngine: \"musescore\",\n    scoreRebuildRequestId: 0,\n    analysisState: \"idle\",")
replace_once("lib/stores/workspace.tsx", "  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);\n  const setAnalysisState", "  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);\n  const requestScoreRebuild = useCallback(() => setWorkspace((prev) => ({ ...prev, scoreRebuildRequestId: prev.scoreRebuildRequestId + 1 })), []);\n  const setAnalysisState")
replace_once("lib/stores/workspace.tsx", "      setScoreEngine,\n      setAnalysisState,", "      setScoreEngine,\n      requestScoreRebuild,\n      setAnalysisState,")

replace_once("components/workspace/WorkspaceSession.tsx", "  startCompareWorkflow,\n  startUnderstandWorkflow,", "  startCompareWorkflow,\n  startScoreWorkflow,\n  startUnderstandWorkflow,")
replace_once("components/workspace/WorkspaceSession.tsx", "import { buildPlaybackSources } from \"@/lib/playback-sources\";", "import { buildPlaybackSources } from \"@/lib/playback-sources\";\nimport { selectScoreArtifacts } from \"@/lib/score-artifacts\";")
replace_once("components/workspace/WorkspaceSession.tsx", "  const initializedProjectSelectionRef = useRef<string | null>(null);", "  const initializedProjectSelectionRef = useRef<string | null>(null);\n  const performanceMidiVersionRef = useRef<string | null>(null);")
replace_once("components/workspace/WorkspaceSession.tsx", "        setAnalysisState(\"analyzing\");", "        if (activeJob.capability.name !== \"score\") setAnalysisState(\"analyzing\");")
replace_once("components/workspace/WorkspaceSession.tsx", "        setMessage(understandStageLabel(activeJob.lifecycle.progress));", "        setMessage(activeJob.capability.name === \"score\" ? \"Rebuilding Score…\" : understandStageLabel(activeJob.lifecycle.progress));")
replace_once(
    "components/workspace/WorkspaceSession.tsx",
    '''      const original = latestByKind.get("audio_original");\n      const baseMidi = latestByKind.get("midi_performance");\n      const midi = baseMidi ?? latestByKind.get("midi_corrected");\n      const score = latestByKind.get("musicxml_score");\n      const renderedScore = latestByKind.get("rendered_score");''',
    '''      const original = latestByKind.get("audio_original");\n      const baseMidi = latestByKind.get("midi_performance");\n      performanceMidiVersionRef.current = baseMidi?.latest_version?.id ?? null;\n      const midi = baseMidi ?? latestByKind.get("midi_corrected");\n      const { score, renderedScore } = selectScoreArtifacts(\n        bundle,\n        performanceMidiVersionRef.current,\n        scoreEngine,\n      );''',
)
replace_once("components/workspace/WorkspaceSession.tsx", "  }, [clearProcessingRefresh, queryClient, replaceRepresentations, replaceSources, resetTimeline, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);", "  }, [clearProcessingRefresh, queryClient, replaceRepresentations, replaceSources, resetTimeline, scoreEngine, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);")
replace_once("components/workspace/WorkspaceSession.tsx", "  const handledStudioAction = useRef(0);", "  const handledScoreRebuildRequest = useRef(workspace.scoreRebuildRequestId);\n  const handledStudioAction = useRef(0);")
marker = '''  useEffect(() => {\n    if (projectQuery.isError || worksQuery.isError) {'''
effect = '''  useEffect(() => {\n    const requestId = workspace.scoreRebuildRequestId;\n    if (!requestId || requestId === handledScoreRebuildRequest.current || !projectId || !workspace.activeWorkId) return;\n    handledScoreRebuildRequest.current = requestId;\n\n    const workId = workspace.activeWorkId;\n    const performanceMidiVersionId = performanceMidiVersionRef.current;\n    if (!performanceMidiVersionId) {\n      setError("A canonical performance MIDI is required before rebuilding Score.");\n      setStage("error");\n      return;\n    }\n\n    void (async () => {\n      setError(null);\n      setProgress(0);\n      setProcessingWorkId(workId);\n      setStage("processing");\n      setMessage(`Rebuilding Score with ${scoreEngine === "pm2s" ? "PM2S" : "MuseScore"}…`);\n      try {\n        const { job } = await startScoreWorkflow(performanceMidiVersionId, projectId, scoreEngine);\n        setActiveJobId(job.id);\n        await loadWork(workId);\n      } catch (cause) {\n        setActiveJobId(null);\n        setError(cause instanceof Error ? cause.message : "Could not rebuild Score");\n        setStage("error");\n      }\n    })();\n  }, [loadWork, projectId, scoreEngine, workspace.activeWorkId, workspace.scoreRebuildRequestId]);\n\n'''
replace_once("components/workspace/WorkspaceSession.tsx", marker, effect + marker)

replace_once("components/workspace/RepresentationStack.tsx", "  const { workspace, requestImport, setActiveRepresentation, clearSelection } = useWorkspace();", "  const { workspace, requestImport, requestScoreRebuild, setActiveRepresentation, clearSelection } = useWorkspace();")
toolbar_marker = '''        {preparingRepresentations && (\n          <span\n            className="muted"\n            role="status"\n            style={{ alignSelf: "center", fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}\n          >\n            Preparing representations…\n          </span>\n        )}'''
toolbar_replacement = toolbar_marker + '''\n        <div\n          aria-label="Score controls"\n          style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-2)" }}\n        >\n          <span className="muted" style={{ fontSize: "var(--fs-xs)", whiteSpace: "nowrap" }}>Score</span>\n          <ScoreEngineToggle />\n          <button type="button" className="btn" onClick={requestScoreRebuild}>Rebuild Score</button>\n        </div>'''
replace_once("components/workspace/RepresentationStack.tsx", toolbar_marker, toolbar_replacement)
