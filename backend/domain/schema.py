import json
from pathlib import Path

from .models import (
    Alignment,
    Artifact,
    Entity,
    Insight,
    Job,
    JobLifecycle,
    Project,
    Selection,
    Span,
    Version,
    Work,
    Workflow,
)


def export_json_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    schemas = {
        "Project": Project.model_json_schema(),
        "Work": Work.model_json_schema(),
        "Artifact": Artifact.model_json_schema(),
        "Version": Version.model_json_schema(),
        "Entity": Entity.model_json_schema(),
        "Insight": Insight.model_json_schema(),
        "Alignment": Alignment.model_json_schema(),
        "Workflow": Workflow.model_json_schema(),
        "Job": Job.model_json_schema(),
        "JobLifecycle": JobLifecycle.model_json_schema(),
        "Selection": Selection.model_json_schema(),
        "Span": Span.model_json_schema(),
    }

    manifest: dict[str, str] = {}
    for name, schema in schemas.items():
        filename = f"{name}.schema.json"
        manifest[name] = filename
        (output_dir / filename).write_text(json.dumps(schema, indent=2))

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
