"""Contract-level guards for the generated OpenAPI document."""

from backend.main import app

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def test_successful_json_responses_have_explicit_schemas() -> None:
    schema = app.openapi()
    missing: list[str] = []

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS:
                continue
            for status, response in operation.get("responses", {}).items():
                if not str(status).startswith("2"):
                    continue
                json_response = response.get("content", {}).get("application/json")
                if json_response is None:
                    continue
                if not json_response.get("schema"):
                    missing.append(f"{method.upper()} {path} -> {status}")

    assert missing == [], "Untyped successful JSON responses: " + ", ".join(missing)
