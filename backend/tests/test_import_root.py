import pathlib


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _backend_qualified_imports(path: pathlib.Path) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        statement = line.strip()
        if statement.startswith("from backend ") or statement.startswith("from backend."):
            imports.append((lineno, statement))
        elif statement.startswith("import backend ") or statement.startswith("import backend."):
            imports.append((lineno, statement))
    return imports


def test_backend_has_one_python_import_root() -> None:
    offenders: list[str] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        for lineno, statement in _backend_qualified_imports(path):
            relative = path.relative_to(BACKEND_ROOT)
            offenders.append(f"{relative}:{lineno}: {statement}")

    assert not offenders, (
        "backend/ is the canonical Python import root; use imports such as "
        "`evaluation.*` or `domain.*`, never `backend.evaluation.*` / `backend.domain.*`.\n"
        + "\n".join(offenders)
    )
