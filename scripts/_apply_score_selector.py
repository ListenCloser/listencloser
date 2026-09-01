from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1))


# API contract + idempotency identity.
replace_once(
    "backend/domain/api.py",
    '''class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transcription_profile: Literal["auto", "solo_piano"] | None = None


def _canonical_transcription_profile(profile: str | None) -> str:
    """Normalize the transcription profile for workflow identity.

    ``None`` (omitted) and ``"auto"`` are the same request semantically (the
    default general engine). Normalizing avoids duplicate cache entries while
    still distinguishing ``auto`` from ``solo_piano`` so re-requesting the same
    version with a different profile creates a distinct job rather than
    returning a stale cached one.
    """
    return profile or "auto"
''',
    '''class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transcription_profile: Literal["auto", "solo_piano"] | None = None
    score_engine: Literal["musescore", "pm2s"] | None = None


def _canonical_transcription_profile(profile: str | None) -> str:
    """Normalize the transcription profile for workflow identity.

    ``None`` (omitted) and ``"auto"`` are the same request semantically (the
    default general engine). Normalizing avoids duplicate cache entries while
    still distinguishing ``auto`` from ``solo_piano`` so re-requesting the same
    version with a different profile creates a distinct job rather than
    returning a stale cached one.
    """
    return profile or "auto"


def _canonical_score_engine(engine: str | None) -> str:
    """Normalize omitted Score selection to the current MuseScore baseline."""
    return engine or "musescore"
''',
)
replace_once(
    "backend/domain/api.py",
    '''        version = _require_version_in_project(sb, version_id, project_id, owner_id)
        profile = _canonical_transcription_profile(body.transcription_profile)

        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:understand:1.0:{owner_id}:{version_id}:{profile}",
        )
''',
    '''        version = _require_version_in_project(sb, version_id, project_id, owner_id)
        profile = _canonical_transcription_profile(body.transcription_profile)
        score_engine = _canonical_score_engine(body.score_engine)

        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:understand:1.0:{owner_id}:{version_id}:{profile}:{score_engine}",
        )
''',
)
replace_once(
    "backend/domain/api.py",
    'f"hello-ai:understand-workflow:1.0:{owner_id}:{version_id}:{profile}"',
    'f"hello-ai:understand-workflow:1.0:{owner_id}:{version_id}:{profile}:{score_engine}"',
)
replace_once(
    "backend/domain/api.py",
    '''                "fmt": Path(version.label).suffix.lstrip(".").lower() or "wav",
                "transcription_profile": profile,
            },
            cache_key=f"understand:1.0:{owner_id}:{version_id}:{profile}",
''',
    '''                "fmt": Path(version.label).suffix.lstrip(".").lower() or "wav",
                "transcription_profile": profile,
                "score_engine": score_engine,
            },
            cache_key=f"understand:1.0:{owner_id}:{version_id}:{profile}:{score_engine}",
''',
)

# Explicit notation-engine routing through the existing boundary.
replace_once(
    "backend/music_features.py",
    '''def notation_with_engine(midi_bytes: bytes, beat_times: list[float], **kwargs: Any) -> dict:
    """Create notation using the configured notation engine.

    Returns a dict with notation_midi, musicxml, quantization_report, and provenance.
    Keyword arguments are forwarded to the engine's convert method (e.g. adaptive,
    downbeats, beat_positions, notation_ready, piano_grand_staff).
    """
    from engines.registry import get_notation_engine

    engine = get_notation_engine()
''',
    '''def notation_with_engine(
    midi_bytes: bytes,
    beat_times: list[float],
    *,
    engine_name: str | None = None,
    **kwargs: Any,
) -> dict:
    """Create notation using an explicit or configured notation engine.

    Returns a dict with notation_midi, musicxml, quantization_report, and provenance.
    Keyword arguments are forwarded to the engine's convert method (e.g. adaptive,
    downbeats, beat_positions, notation_ready, piano_grand_staff).
    """
    from engines.registry import get_notation_engine

    engine = get_notation_engine(engine_name)
''',
)

# Durable score job routing + provenance. Initialize optional beat evidence so a
# score-only job cannot reference variables that only exist in the audio branch.
replace_once(
    "backend/domain/capabilities.py",
    '''    midi_bytes = download_version_bytes(input_version, client)
    beat_times: list[float] = []
    tempo = 0.0
    if len(job.input_version_ids) > 1:
''',
    '''    midi_bytes = download_version_bytes(input_version, client)
    beat_times: list[float] = []
    beat_result = None
    downbeats = None
    tempo = 0.0
    score_engine = str(job.parameters.get("score_engine") or "musescore")
    if len(job.input_version_ids) > 1:
''',
)
replace_once(
    "backend/domain/capabilities.py",
    '''        notation_result = music_features.notation_with_engine(
            midi_bytes,
            beat_times,
            downbeats=downbeats,
''',
    '''        notation_result = music_features.notation_with_engine(
            midi_bytes,
            beat_times,
            engine_name=score_engine,
            downbeats=downbeats,
''',
)
replace_once(
    "backend/domain/capabilities.py",
    '''    notation_midi = notation_result["notation_midi"]
    notation_report = notation_result["quantization_report"]
''',
    '''    notation_midi = notation_result["notation_midi"]
    notation_report = notation_result["quantization_report"]
    notation_provenance = notation_result["provenance"]
''',
)
replace_once(
    "backend/domain/capabilities.py",
    '''        metadata={
            "notation": notation_report,
            "estimated_tempo_bpm": tempo,
            "beat_provenance": beat_result.get("provenance"),
        },
''',
    '''        metadata={
            "notation": notation_report,
            "provenance": notation_provenance,
            "score_engine_requested": score_engine,
            "estimated_tempo_bpm": tempo,
            "beat_provenance": beat_result.get("provenance") if beat_result else None,
        },
''',
)
replace_once(
    "backend/domain/capabilities.py",
    '''            "notation_midi_version_id": str(notation_version_id),
            "notation": notation_report,
            "quality_notice": "Derived from automatic transcription; review by ear before sharing.",
''',
    '''            "notation_midi_version_id": str(notation_version_id),
            "notation": notation_report,
            "provenance": notation_provenance,
            "score_engine_requested": score_engine,
            "quality_notice": "Derived from automatic transcription; review by ear before sharing.",
''',
)

# API idempotency regression coverage.
replace_once(
    "backend/tests/test_transcription_profile_routing.py",
    '''            assert params["transcription_profile"] == "solo_piano"
            assert params["fmt"] == "m4a"
''',
    '''            assert params["transcription_profile"] == "solo_piano"
            assert params["score_engine"] == "musescore"
            assert params["fmt"] == "m4a"
''',
)
replace_once(
    "backend/tests/test_transcription_profile_routing.py",
    '''            assert params["transcription_profile"] == "auto"
            assert params["fmt"] == "m4a"
''',
    '''            assert params["transcription_profile"] == "auto"
            assert params["score_engine"] == "musescore"
            assert params["fmt"] == "m4a"
''',
)
replace_once(
    "backend/tests/test_transcription_profile_routing.py",
    '''    def test_understand_same_profile_is_idempotent(self, monkeypatch):
''',
    '''    def test_understand_score_engine_is_part_of_idempotency_identity(self, monkeypatch):
        client, job_repo, version, owner = self._client(monkeypatch)
        try:
            base = {
                "version_id": version.id,
                "project_id": "00000000-0000-0000-0000-000000000020",
                "transcription_profile": "solo_piano",
            }
            baseline = client.post(
                "/api/v1/workflows/understand",
                json={**base, "score_engine": "musescore"},
            )
            challenger = client.post(
                "/api/v1/workflows/understand",
                json={**base, "score_engine": "pm2s"},
            )

            assert baseline.status_code == 200
            assert challenger.status_code == 200
            assert len(job_repo.created) == 2
            assert job_repo.created[0].id != job_repo.created[1].id
            assert job_repo.created[0].cache_key != job_repo.created[1].cache_key
            assert job_repo.created[0].parameters["score_engine"] == "musescore"
            assert job_repo.created[1].parameters["score_engine"] == "pm2s"
        finally:
            from auth_utils import verify_token
            from main import app

            app.dependency_overrides.pop(verify_token, None)

    def test_understand_omitted_score_engine_matches_explicit_musescore(self, monkeypatch):
        client, job_repo, version, owner = self._client(monkeypatch)
        try:
            base = {
                "version_id": version.id,
                "project_id": "00000000-0000-0000-0000-000000000020",
            }
            omitted = client.post("/api/v1/workflows/understand", json=base)
            explicit = client.post(
                "/api/v1/workflows/understand",
                json={**base, "score_engine": "musescore"},
            )

            assert omitted.status_code == 200
            assert explicit.status_code == 200
            assert omitted.json()["job"]["id"] == explicit.json()["job"]["id"]
            assert len(job_repo.created) == 1
        finally:
            from auth_utils import verify_token
            from main import app

            app.dependency_overrides.pop(verify_token, None)

    def test_understand_same_profile_is_idempotent(self, monkeypatch):
''',
)

Path("backend/tests/test_score_engine_routing.py").write_text(
    '''"""Focused regression coverage for explicit Score-engine routing."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from domain.models import Capability, Job
from engines.base import EngineProvenance, NotationResult


def test_notation_with_engine_routes_explicit_engine(monkeypatch):
    import engines.registry as registry
    import music_features

    selected = {}

    class FakeNotationEngine:
        def convert(self, midi_bytes, beat_times, **kwargs):
            return NotationResult(
                notation_midi=b"MThd-score",
                musicxml=b"<score-partwise/>",
                quantization_report={"engine": "pm2s"},
                provenance=EngineProvenance(engine="pm2s", library_version="test"),
            )

    def fake_get_notation_engine(name=None):
        selected["name"] = name
        return FakeNotationEngine()

    monkeypatch.setattr(registry, "get_notation_engine", fake_get_notation_engine)
    result = music_features.notation_with_engine(b"MThd-performance", [], engine_name="pm2s")

    assert selected["name"] == "pm2s"
    assert result["provenance"]["engine"] == "pm2s"


def test_handle_score_reads_explicit_engine_without_audio_beat_input(monkeypatch):
    from domain import capabilities

    input_version_id = uuid4()
    workflow_id = uuid4()
    work_id = uuid4()
    job = Job(
        workflow_id=workflow_id,
        capability=Capability(name="score", version="1.0"),
        input_version_ids=[input_version_id],
        parameters={"score_engine": "pm2s"},
    )
    input_version = SimpleNamespace(id=input_version_id)
    captured = {}
    created_metadata = []

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda client, workflow: "owner-1")
    monkeypatch.setattr(capabilities, "_lookup_version", lambda client, version_id: input_version)
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda client, version_id: work_id)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *args, **kwargs: b"performance")
    monkeypatch.setattr(capabilities, "_upload_bytes", lambda *args, **kwargs: None)

    def fake_create_output_version(*args, **kwargs):
        created_metadata.append(kwargs.get("metadata") or {})
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_output_version", fake_create_output_version)

    def fake_notation(midi_bytes, beat_times, **kwargs):
        captured.update(kwargs)
        return {
            "notation_midi": b"MThd-score",
            "musicxml": b"<score-partwise/>",
            "quantization_report": {"engine": "pm2s"},
            "provenance": {"engine": "pm2s", "library_version": "test"},
        }

    monkeypatch.setattr(capabilities.music_features, "notation_with_engine", fake_notation)
    monkeypatch.setattr(capabilities.music_features, "midi_to_wav", lambda midi_bytes: b"wav")
    monkeypatch.setattr(capabilities.music_features, "measure_start_seconds", lambda midi_bytes: [])

    output_ids = capabilities.handle_score(job, SimpleNamespace())

    assert captured["engine_name"] == "pm2s"
    assert captured["downbeats"] is None
    assert len(output_ids) == 3
    assert any(metadata.get("score_engine_requested") == "pm2s" for metadata in created_metadata)
    assert any(metadata.get("provenance", {}).get("engine") == "pm2s" for metadata in created_metadata)
'''
)

# Frontend workspace state + compact import control.
replace_once(
    "lib/stores/workspace.tsx",
    'export type TranscriptionProfile = "auto" | "solo_piano";\n',
    'export type TranscriptionProfile = "auto" | "solo_piano";\nexport type ScoreEngine = "musescore" | "pm2s";\n',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''  selection: MusicalSelection | null;
  transcriptionProfile: TranscriptionProfile;
  analysisState: AnalysisState;
''',
    '''  selection: MusicalSelection | null;
  transcriptionProfile: TranscriptionProfile;
  scoreEngine: ScoreEngine;
  analysisState: AnalysisState;
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''  clearSelection: () => void;
  setTranscriptionProfile: (profile: TranscriptionProfile) => void;
  setAnalysisState: (state: AnalysisState) => void;
''',
    '''  clearSelection: () => void;
  setTranscriptionProfile: (profile: TranscriptionProfile) => void;
  setScoreEngine: (engine: ScoreEngine) => void;
  setAnalysisState: (state: AnalysisState) => void;
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''    selection: null,
    transcriptionProfile: "auto",
    analysisState: "idle",
''',
    '''    selection: null,
    transcriptionProfile: "auto",
    scoreEngine: "musescore",
    analysisState: "idle",
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''  const setTranscriptionProfile = useCallback((transcriptionProfile: TranscriptionProfile) => setWorkspace((prev) => prev.transcriptionProfile === transcriptionProfile ? prev : { ...prev, transcriptionProfile }), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);
''',
    '''  const setTranscriptionProfile = useCallback((transcriptionProfile: TranscriptionProfile) => setWorkspace((prev) => prev.transcriptionProfile === transcriptionProfile ? prev : { ...prev, transcriptionProfile }), []);
  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);
''',
)
replace_once(
    "lib/stores/workspace.tsx",
    '''      clearSelection,
      setTranscriptionProfile,
      setAnalysisState,
''',
    '''      clearSelection,
      setTranscriptionProfile,
      setScoreEngine,
      setAnalysisState,
''',
)

replace_once(
    "components/workspace/RepresentationStack.tsx",
    'import { useWorkspace, type TranscriptionProfile } from "@/lib/stores/workspace";',
    'import { useWorkspace, type ScoreEngine, type TranscriptionProfile } from "@/lib/stores/workspace";',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '''function WorkspaceLoadingSkeleton() {
''',
    '''function ScoreEngineToggle() {
  const { workspace, setScoreEngine } = useWorkspace();
  const options: { id: ScoreEngine; label: string; description: string }[] = [
    { id: "musescore", label: "MuseScore", description: "Current notation baseline" },
    {
      id: "pm2s",
      label: "PM2S",
      description: "Experimental learned piano score reconstruction",
    },
  ];
  return (
    <div className="transcription-mode" role="group" aria-label="Score interpretation">
      {options.map((option) => (
        <Tooltip key={option.id} content={option.description}>
          <button
            type="button"
            aria-pressed={workspace.scoreEngine === option.id}
            className={workspace.scoreEngine === option.id ? "active" : ""}
            onClick={() => setScoreEngine(option.id)}
          >
            {option.label}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}

function WorkspaceLoadingSkeleton() {
''',
)
replace_once(
    "components/workspace/RepresentationStack.tsx",
    '''        <details className="transcription-settings">
          <summary>Transcription</summary>
          <TranscriptionModeToggle />
        </details>
''',
    '''        <details className="transcription-settings">
          <summary>Processing</summary>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Transcription</span>
          <TranscriptionModeToggle />
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Score interpretation</span>
          <ScoreEngineToggle />
        </details>
''',
)

# Typed API call and both workflow-start call sites.
replace_once(
    "lib/api-client.ts",
    '''type TranscriptionProfile = NonNullable<
  components["schemas"]["UnderstandWorkflowBody"]["transcription_profile"]
>;
''',
    '''type TranscriptionProfile = NonNullable<
  components["schemas"]["UnderstandWorkflowBody"]["transcription_profile"]
>;
type ScoreEngine = NonNullable<components["schemas"]["UnderstandWorkflowBody"]["score_engine"]>;
''',
)
replace_once(
    "lib/api-client.ts",
    '''export async function startUnderstandWorkflow(
  versionId: string,
  projectId: string,
  transcriptionProfile?: TranscriptionProfile,
): Promise<{ workflow: Workflow; job: Job }> {
''',
    '''export async function startUnderstandWorkflow(
  versionId: string,
  projectId: string,
  transcriptionProfile?: TranscriptionProfile,
  scoreEngine?: ScoreEngine,
): Promise<{ workflow: Workflow; job: Job }> {
''',
)
replace_once(
    "lib/api-client.ts",
    '''        ...(transcriptionProfile ? { transcription_profile: transcriptionProfile } : {}),
      },
''',
    '''        ...(transcriptionProfile ? { transcription_profile: transcriptionProfile } : {}),
        ...(scoreEngine ? { score_engine: scoreEngine } : {}),
      },
''',
)

replace_once(
    "app/page.tsx",
    '''  const transcriptionProfile = workspace.transcriptionProfile;
  const { replaceSources } = useTransport();
''',
    '''  const transcriptionProfile = workspace.transcriptionProfile;
  const scoreEngine = workspace.scoreEngine;
  const { replaceSources } = useTransport();
''',
)
replace_once(
    "app/page.tsx",
    '''        const measureStarts = (renderedScore?.latest_version?.metadata?.measure_starts_seconds as number[] | undefined) ?? [];
        return {
''',
    '''        const measureStarts = (renderedScore?.latest_version?.metadata?.measure_starts_seconds as number[] | undefined) ?? [];
        const scoreEngineMetadata = score.latest_version?.metadata?.score_engine_requested;
        const scoreProvenance = scoreEngineMetadata === "pm2s"
          ? "PM2S · MuseScore import"
          : scoreEngineMetadata === "musescore"
            ? "MuseScore"
            : "score interpretation";
        return {
''',
)
replace_once(
    "app/page.tsx",
    '          provenance: "music21 notation",',
    '          provenance: scoreProvenance,',
)
replace_once(
    "app/page.tsx",
    'const { job } = await startUnderstandWorkflow(version.id, projectId, transcriptionProfile);',
    'const { job } = await startUnderstandWorkflow(version.id, projectId, transcriptionProfile, scoreEngine);',
)
replace_once(
    "app/page.tsx",
    '''  }, [loadWork, projectId, queryClient, serviceStatus, setActiveWorkId, transcriptionProfile]);
''',
    '''  }, [loadWork, projectId, queryClient, scoreEngine, serviceStatus, setActiveWorkId, transcriptionProfile]);
''',
)
replace_once(
    "app/page.tsx",
    'const { job } = await startUnderstandWorkflow(pendingSourceVersionId, projectId, transcriptionProfile);',
    'const { job } = await startUnderstandWorkflow(pendingSourceVersionId, projectId, transcriptionProfile, scoreEngine);',
)
replace_once(
    "app/page.tsx",
    '''  }, [loadWork, pendingSourceVersionId, processingWorkId, projectId, transcriptionProfile, workspace.activeWorkId]);
''',
    '''  }, [loadWork, pendingSourceVersionId, processingWorkId, projectId, scoreEngine, transcriptionProfile, workspace.activeWorkId]);
''',
)

# Keep the real-checkpoint smoke in the normal backend-image gate. One native
# architecture is enough to prove checkpoint/model compatibility; both images
# still build and import PM2S independently.
replace_once(
    ".github/workflows/backend-image.yml",
    '''      - name: Measure persistent Numba cache for explicit librosa rollback
''',
    '''      - name: Run PM2S production score smoke
        if: matrix.arch == 'amd64'
        env:
          ARCH: ${{ matrix.arch }}
        run: |
          docker run --rm \\
            --entrypoint python \\
            "hello-ai-backend:${ARCH}" \\
            scripts/smoke_pm2s.py
      - name: Measure persistent Numba cache for explicit librosa rollback
''',
)
