"""Export the FastAPI schema without requiring a running development server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main import app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "openapi" / "openapi.json"


def export_openapi(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
