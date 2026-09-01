from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _backend_qualified_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "backend" or alias.name.startswith("backend."):
                    imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "backend" or module.startswith("backend.")):
                imports.append((node.lineno, module))

    return imports


def test_backend_has_one_python_import_root() -> None:
    offenders: list[str] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        for lineno, module in _backend_qualified_imports(path):
            relative = path.relative_to(BACKEND_ROOT)
            offenders.append(f"{relative}:{lineno}: {module}")

    assert not offenders, (
        "backend/ is the canonical Python import root; use imports such as "
        "`evaluation.*` or `domain.*`, never `backend.evaluation.*` / `backend.domain.*`.\n"
        + "\n".join(offenders)
    )
