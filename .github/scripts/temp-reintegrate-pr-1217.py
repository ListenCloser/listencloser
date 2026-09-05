from pathlib import Path
import json
import re
import subprocess
import tempfile


def run(*args: str) -> None:
    subprocess.run(args, check=True)


# Keep the current capability registry and add only the bounded Layers entry.
capabilities = Path("backend/config/capabilities.json")
data = json.loads(capabilities.read_text())
registry = data["capabilities"]
registry["source_separation"] = {
    "status": "experimental",
    "input": "audio",
    "engine": "demucs_4.1.0_htdemucs_955717e8",
    "exposure": {"inspector": False, "annotations": False, "ask": False},
    "model": {
        "name": "htdemucs",
        "version": "955717e8",
        "checkpoint": "adefossez/HTDemucs/955717e8.safetensors",
        "checkpoint_sha256": "d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd",
        "code_license": "MIT",
        "checkpoint_license": "MIT",
    },
    "validated_domain": "optional within-recording four-stem isolation and playback only",
    "notes": (
        "User-triggered only; never universal preprocessing. Produces exactly "
        "vocals/drums/bass/other with CPU shifts=0, preserves exact source Version + "
        "producing Job lineage, and exposes complete succeeded sets only through the "
        "existing playback-source selector. Partial, failed, cancelled, or mixed-job "
        "outputs remain hidden."
    ),
}
capabilities.write_text(json.dumps(data, indent=2) + "\n")

# Preserve all newer public-create capabilities and add deterministic separation
# creation for exact Original-audio Versions.
workflows = Path("backend/domain/api/workflows_jobs.py")
text = workflows.read_text()
set_pattern = re.compile(
    r"_PUBLIC_CREATE_WORKFLOW_ACTIONS = frozenset\(\s*\{([^}]*)\}\s*\)", re.S
)
match = set_pattern.search(text)
if not match:
    raise RuntimeError("public workflow allowlist not found")
actions = set(re.findall(r'"([^"]+)"', match.group(1)))
actions.add("separate")
rendered = "_PUBLIC_CREATE_WORKFLOW_ACTIONS = frozenset(\n    {" + ", ".join(
    f'"{item}"' for item in sorted(actions)
) + "}\n)"
text = text[: match.start()] + rendered + text[match.end() :]
if "_SEPARATION_MODEL_SIGNATURE" not in text:
    marker = rendered + "\n"
    if marker not in text:
        raise RuntimeError("separation signature insertion anchor not found")
    text = text.replace(
        marker,
        marker + '_SEPARATION_MODEL_SIGNATURE = "955717e8"\n',
        1,
    )

old = '''        capability_name = _require_public_create_action(body.action)
        _require_version_in_project(sb, version_id, project_id, owner)

        workflow = Workflow('''
if old in text:
    separation_block = '''        capability_name = _require_public_create_action(body.action)
        version = _require_version_in_project(sb, version_id, project_id, owner)

        if capability_name == "separate":
            artifact = ArtifactRepo(sb).get(version.artifact_id, owner)
            if not artifact:
                raise HTTPException(status_code=404, detail="Artifact not found")
            if artifact.kind != ArtifactKind.audio_original:
                raise HTTPException(
                    status_code=400,
                    detail="Layer separation requires an Original audio Version",
                )

            # Optional separation targets the exact Original so its durable Job
            # is discoverable from the Work bundle on reload. Product isolation
            # is enforced by the workspace's optional-capability state filter,
            # not by hiding the Job from durable Work truth.
            separation_identity = f"{owner}:{version_id}:{_SEPARATION_MODEL_SIGNATURE}"
            job_id = uuid5(
                NAMESPACE_URL,
                f"listencloser:separate:1.0:{separation_identity}",
            )
            job_repo = JobRepo(sb)
            existing_job = job_repo.get(job_id, owner)
            if existing_job:
                workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner)
                if not workflow:
                    raise RuntimeError("idempotent separation job references a missing workflow")
                return {"workflow": workflow, "job": existing_job}

            workflow = Workflow(
                id=uuid5(
                    NAMESPACE_URL,
                    f"listencloser:separate-workflow:1.0:{separation_identity}",
                ),
                project_id=project_id,
                kind=WorkflowKind.create,
                target_version_id=version_id,
                parameters={
                    "action": "separate",
                    "source_version_id": str(version_id),
                    "model": "htdemucs",
                    "model_signature": _SEPARATION_MODEL_SIGNATURE,
                    "shifts": 0,
                },
            )
            workflow_repo = WorkflowRepo(sb)
            try:
                workflow = workflow_repo.create(workflow, owner)
            except Exception:
                concurrent_job = job_repo.get(job_id, owner)
                if concurrent_job:
                    concurrent_workflow = workflow_repo.get(concurrent_job.workflow_id, owner)
                    if concurrent_workflow:
                        return {"workflow": concurrent_workflow, "job": concurrent_job}
                workflow = workflow_repo.get(workflow.id, owner)
                if not workflow:
                    raise

            parameters = {
                "fmt": Path(version.label).suffix.lstrip(".").lower() or "wav",
                "model": "htdemucs",
                "model_signature": _SEPARATION_MODEL_SIGNATURE,
                "shifts": 0,
            }
            job = Job(
                id=job_id,
                workflow_id=workflow.id,
                capability=Capability(name="separate", version="1.0"),
                input_version_ids=[version_id],
                parameters=parameters,
                cache_key=f"separate:1.0:{separation_identity}:shifts=0",
                created_by=owner,
            )
            try:
                job = job_repo.create(job, owner)
            except Exception:
                job = job_repo.get(job_id, owner)
                if not job:
                    raise
            return {"workflow": workflow, "job": job}

        workflow = Workflow('''
    text = text.replace(old, separation_block, 1)
elif 'capability_name == "separate"' not in text:
    raise RuntimeError("create-workflow separation insertion seam not found")
workflows.write_text(text)

# Preserve every newer worker capability and register source separation once.
worker = Path("backend/worker.py")
text = worker.read_text()
source_import = "from domain.source_separation import register_source_separation\n"
if source_import not in text:
    anchor = "from domain.structure_map_capability import register_structure_map_capability\n"
    if anchor not in text:
        raise RuntimeError("worker source-separation import anchor not found")
    text = text.replace(anchor, source_import + anchor, 1)
source_call = "    register_source_separation(worker)\n"
if source_call not in text:
    anchor = "    register_structure_map_capability(worker)\n"
    if anchor not in text:
        raise RuntimeError("worker source-separation registration anchor not found")
    text = text.replace(anchor, anchor + source_call, 1)
worker.write_text(text)

# Optional analysis jobs must not replace Work-level Understand/Score state.
session = Path("components/workspace/WorkspaceSession.tsx")
text = session.read_text()
optional_pattern = re.compile(
    r"const OPTIONAL_ANALYSIS_CAPABILITIES = new Set\(\[([^\]]*)\]\);"
)
match = optional_pattern.search(text)
if not match:
    raise RuntimeError("WorkspaceSession optional-analysis set not found")
values = set(re.findall(r'"([^"]+)"', match.group(1)))
values.add("separate")
rendered_optional = "const OPTIONAL_ANALYSIS_CAPABILITIES = new Set([" + ", ".join(
    f'"{value}"' for value in sorted(values)
) + "]);"
text = text[: match.start()] + rendered_optional + text[match.end() :]
session.write_text(text)

# Merge Layers into the one existing Add-analysis chooser rather than restoring
# the stale two-capability StructureMap surface from the old branch.
structure = Path("components/workspace/StructureMap.tsx")
text = structure.read_text()
layer_import = 'import { useLayerAnalysis } from "@/components/workspace/useLayerAnalysis";\n'
if layer_import not in text:
    anchor = 'import AddAnalysis, { type AddAnalysisOption } from "@/components/workspace/AddAnalysis";\n'
    if anchor not in text:
        raise RuntimeError("StructureMap AddAnalysis import anchor not found")
    text = text.replace(anchor, anchor + layer_import, 1)
if "export default function StructureMap()" in text:
    text = text.replace(
        "export default function StructureMap() {",
        "export default function StructureMap({ canProcess = false }: { canProcess?: boolean }) {",
        1,
    )
elif "canProcess?: boolean" not in text:
    raise RuntimeError("StructureMap function signature seam not found")
hook_line = "  const layerAnalysis = useLayerAnalysis(canProcess);\n"
if hook_line not in text:
    anchor = "  const { transport, seek, play, setActiveSource, audioRef } = useTransport();\n"
    if anchor not in text:
        raise RuntimeError("StructureMap transport hook anchor not found")
    text = text.replace(anchor, anchor + hook_line, 1)
layer_effect = '''  // Layers owns its durable job state but discovery remains in the shared chooser.
  useEffect(() => {
    if (layerAnalysis.option?.busy || layerAnalysis.notice) setChooserOpen(true);
  }, [layerAnalysis.notice, layerAnalysis.option?.busy]);

'''
if "layerAnalysis.option?.busy || layerAnalysis.notice" not in text:
    anchor = '''  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activeJobId;
'''
    if anchor not in text:
        raise RuntimeError("StructureMap layer effect anchor not found")
    text = text.replace(anchor, layer_effect + anchor, 1)
layer_option = '''  if (layerAnalysis.option) {
    analysisOptions.push(layerAnalysis.option);
  }
'''
if "analysisOptions.push(layerAnalysis.option)" not in text:
    anchor = "  if (hasExactSelectedPassage) {\n"
    if anchor not in text:
        raise RuntimeError("StructureMap analysis-options anchor not found")
    text = text.replace(anchor, layer_option + anchor, 1)
text = text.replace(
    '  const notice = [error, pitchError].filter(Boolean).join(" · ") || null;\n',
    '  const notice = [error, pitchError, layerAnalysis.notice].filter(Boolean).join(" · ") || null;\n',
    1,
)
if "layerAnalysis.notice].filter" not in text:
    raise RuntimeError("StructureMap chooser notice seam not found")
if "const noticeRole =" not in text:
    anchor = '  const notice = [error, pitchError, layerAnalysis.notice].filter(Boolean).join(" · ") || null;\n'
    text = text.replace(
        anchor,
        anchor
        + '''  const noticeRole = (
    busy
    || pitchBusy
    || observationLost
    || pitchObservationLost
    || (Boolean(layerAnalysis.notice) && layerAnalysis.noticeRole === "status")
  ) ? "status" : "alert";
''',
        1,
    )
old_role = '      noticeRole={busy || pitchBusy || observationLost || pitchObservationLost ? "status" : "alert"}\n'
if old_role in text:
    text = text.replace(old_role, "      noticeRole={noticeRole}\n", 1)
elif "noticeRole={noticeRole}" not in text:
    raise RuntimeError("StructureMap notice-role seam not found")
old_loading = '    if (status === "loading" && pitchStatus === "loading" && !chooserOpen && !pitchReady) return null;\n'
if old_loading in text:
    text = text.replace(
        old_loading,
        '    if (status === "loading" && pitchStatus === "loading" && !chooserOpen && !pitchReady && !layerAnalysis.option) return null;\n',
        1,
    )
structure.write_text(text)

# Add the exact characterized HTDemucs runtime without disturbing newer baked
# models/checkpoints already present in the worker image.
dockerfile = Path("backend/Dockerfile")
text = dockerfile.read_text()
if "Demucs package 4.1.0" not in text:
    anchor = '''RUN /app/.venv/bin/python -c "from beat_this.inference import load_checkpoint; load_checkpoint('final0')" \\
    && sha256sum /app/.cache/torch/hub/checkpoints/beat_this-final0.ckpt \\
    && echo "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331  /app/.cache/torch/hub/checkpoints/beat_this-final0.ckpt" | sha256sum --check -

'''
    if anchor not in text:
        raise RuntimeError("Dockerfile Beat This anchor not found")
    demucs = '''# Experimental Layers keeps the already-characterized HTDemucs candidate from
# #1191. Demucs stays worker-image-only; acquire the exact checkpoint at build
# time, verify its digest, and refuse any runtime model download.
RUN uv pip install --python /app/.venv/bin/python 'cmake==3.31.10' \\
    && CMAKE=/app/.venv/bin/cmake uv pip install --python /app/.venv/bin/python 'demucs==4.1.0' \\
    && uv pip uninstall --python /app/.venv/bin/python cmake

RUN HF_HOME=/app/.cache/huggingface /app/.venv/bin/python -c "import hashlib, importlib.metadata as md; from pathlib import Path; import numpy, torch; from demucs.pretrained import get_model; assert md.version('demucs') == '4.1.0'; assert numpy.__version__ == '1.26.4'; assert torch.__version__.split('+')[0] == '2.6.0'; model=get_model('htdemucs'); assert tuple(model.sources) == ('drums','bass','other','vocals'); matches=list(Path('/app/.cache/huggingface').rglob('955717e8.safetensors')); assert matches, 'verified HTDemucs checkpoint not found'; assert hashlib.sha256(matches[0].read_bytes()).hexdigest() == 'd9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd'"

RUN printf '%s\\n' \\
      "Demucs package 4.1.0" \\
      "Wrapper code license: MIT" \\
      "Wrapper source: https://github.com/adefossez/demucs" \\
      "Model: htdemucs / signature 955717e8" \\
      "Checkpoint: adefossez/HTDemucs/955717e8.safetensors" \\
      "Checkpoint SHA256: d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd" \\
      "Checkpoint license: MIT (author-hosted adefossez/HTDemucs repository)" \\
      "Inference parameters: CPU, shifts=0" \\
      > /app/.cache/HTDEMUCS_LISTENCLOSER_PROVENANCE.txt

'''
    text = text.replace(anchor, anchor + demucs, 1)
if "HF_HUB_OFFLINE=1" not in text:
    anchor = "    TORCH_HOME=/app/.cache/torch \\\n    XDG_CACHE_HOME=/app/.cache \\\n"
    if anchor not in text:
        raise RuntimeError("Dockerfile runtime cache env anchor not found")
    text = text.replace(
        anchor,
        "    TORCH_HOME=/app/.cache/torch \\\n    HF_HOME=/app/.cache/huggingface \\\n    HF_HUB_OFFLINE=1 \\\n    XDG_CACHE_HOME=/app/.cache \\\n",
        1,
    )
dockerfile.write_text(text)

# Match repository formatting/static expectations before pushing the merge.
run("python3", "-m", "pip", "install", "--disable-pip-version-check", "-q", "ruff==0.5.7")
run("ruff", "check", "--fix", "backend/domain/api/workflows_jobs.py", "backend/worker.py")
run("ruff", "format", "backend/domain/api/workflows_jobs.py", "backend/worker.py")
run("npm", "ci")
run("npm", "run", "typecheck")

with tempfile.TemporaryDirectory() as tmp:
    mmd = Path(tmp) / "frontend-dependencies.mmd"
    run(
        "npx",
        "--yes",
        "--package=dependency-cruiser@18.2.0",
        "--package=typescript@5.7.3",
        "depcruise",
        "--config",
        ".dependency-cruiser.cjs",
        "--output-type",
        "mermaid",
        "--include-only",
        "^(app|components|lib)/",
        "--collapse",
        "2",
        "--output-to",
        str(mmd),
        "app",
        "components",
        "lib",
    )
    header = """# Frontend dependency graph

> Generated by dependency-cruiser 18.2.0 with TypeScript 5.7.3 from `.dependency-cruiser.cjs`. Do not hand-edit this graph; regenerate it through the architecture check when frontend imports change.

This is an orientation view of `app/`, `components/`, and `lib/`. Deeper folders are collapsed to keep the graph reviewable. The architecture rules in `.dependency-cruiser.cjs`, not the picture alone, are the enforceable contract.

```mermaid
"""
    Path("docs/generated/frontend-dependencies.md").write_text(
        header + mmd.read_text() + "```\n"
    )
