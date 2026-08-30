#!/usr/bin/env python3
"""Exercise the deployed audio-understanding path through the Vercel app."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _request(
    base_url: str,
    path: str,
    token: str | None = None,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str = "application/json",
) -> dict | list:
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {path} returned {error.code}: {details}"
        ) from error


def _multipart_audio(path: Path) -> tuple[bytes, str]:
    boundary = f"listencloser-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a persisted smoke-test work and verify the deployed "
            "understand pipeline."
        )
    )
    parser.add_argument("audio", type=Path)
    parser.add_argument(
        "--app-url",
        default=os.environ.get("HELLO_AI_APP_URL"),
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("HELLO_AI_PROJECT_ID"),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SUPABASE_ACCESS_TOKEN"),
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    missing = [
        name
        for name, value in {
            "--app-url": args.app_url,
            "--project-id": args.project_id,
            "--token": args.token,
        }.items()
        if not value
    ]
    if missing:
        parser.error(f"missing required configuration: {', '.join(missing)}")
    if not args.audio.is_file():
        parser.error(f"audio file not found: {args.audio}")

    queue = _request(args.app_url, "/api/health/queue")
    if not isinstance(queue, dict) or queue.get("status") != "ready":
        raise RuntimeError(f"queue is not ready: {queue}")

    upload_body, upload_type = _multipart_audio(args.audio)
    uploaded = _request(
        args.app_url,
        f"/api/v1/projects/{args.project_id}/artifacts/upload",
        args.token,
        method="POST",
        body=upload_body,
        content_type=upload_type,
    )
    if not isinstance(uploaded, dict):
        raise RuntimeError("upload returned an invalid response")
    artifact = uploaded["artifact"]
    version = uploaded["version"]

    workflow = _request(
        args.app_url,
        "/api/v1/workflows/understand",
        args.token,
        method="POST",
        body=json.dumps(
            {
                "version_id": version["id"],
                "project_id": args.project_id,
            }
        ).encode(),
    )
    if not isinstance(workflow, dict):
        raise RuntimeError("workflow returned an invalid response")
    job_id = workflow["job"]["id"]
    deadline = time.monotonic() + args.timeout

    while True:
        job = _request(args.app_url, f"/api/v1/jobs/{job_id}", args.token)
        if not isinstance(job, dict):
            raise RuntimeError("job status returned an invalid response")
        print(
            f"{job['stage']:>10} {job['progress'] * 100:6.1f}% "
            f"{job.get('message', '')}",
            flush=True,
        )
        if job["stage"] == "succeeded":
            break
        if job["stage"] in {"failed", "cancelled"}:
            raise RuntimeError(job.get("error") or job.get("message"))
        if time.monotonic() >= deadline:
            raise TimeoutError(f"job {job_id} did not finish in time")
        time.sleep(2)

    bundle = _request(
        args.app_url,
        f"/api/v1/works/{artifact['work_id']}",
        args.token,
    )
    if not isinstance(bundle, dict):
        raise RuntimeError("work bundle returned an invalid response")
    artifacts = bundle["artifacts"]
    kinds = {item["artifact"]["kind"] for item in artifacts}
    expected = {
        "audio_original",
        "audio_rendered",
        "midi_performance",
        "musicxml_score",
    }
    if missing_kinds := expected - kinds:
        raise RuntimeError(f"missing output artifact kinds: {sorted(missing_kinds)}")

    midi = next(
        item
        for item in artifacts
        if item["artifact"]["kind"] == "midi_performance"
    )
    midi_version_id = midi["latest_version"]["id"]
    entities = _request(
        args.app_url,
        f"/api/v1/versions/{midi_version_id}/entities",
        args.token,
    )
    insights = _request(
        args.app_url,
        f"/api/v1/versions/{midi_version_id}/insights",
        args.token,
    )
    if not entities:
        raise RuntimeError("transcription produced no persisted note entities")
    if not insights:
        raise RuntimeError("analysis produced no persisted insights")

    print(
        json.dumps(
            {
                "status": "passed",
                "work_id": artifact["work_id"],
                "job_id": job_id,
                "artifact_kinds": sorted(kinds),
                "entities": len(entities),
                "insights": len(insights),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"smoke test failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
