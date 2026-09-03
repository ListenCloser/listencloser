from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PM2S_CHECKPOINTS = {
    "RNNJointBeatModel.pth": "939e0181f119a473200aece6307906e3dee69d4e2c44abcc878755bf6a18beb6",
    "RNNHandPartModel.pth": "35d0b768fc68f9ec23f77b512ce3cada9b4e9dd816e3ab1c2a1714fa05bc5805",
    "RNNKeySignatureModel.pth": "62ce9004f9a8b3bf24864a5bf15211e1a27c7d2c1eb7071e6672d6d8e265e5de",
    "CNNTimeSignatureModel.pth": "35cd59c456542c1546f870ee639e0c3f87f7b81a48d7f2bfe10dedc89c4d3180",
}


def test_pm2s_checkpoints_are_content_verified_when_downloaded() -> None:
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text()
    pm2s_stage = dockerfile.split("FROM python:3.11-slim AS pm2s", 1)[1].split(
        "FROM python:3.11-slim AS musescore", 1
    )[0]

    checkpoint_pattern = r'"([^":]+\.pth):([0-9a-f]{64})"'
    pinned_checkpoints = dict(re.findall(checkpoint_pattern, pm2s_stage))

    assert pinned_checkpoints == EXPECTED_PM2S_CHECKPOINTS
    checksum_command = 'echo "${expected_sha256}  /opt/pm2s-models/${model}" | sha256sum --check -;'
    assert checksum_command in pm2s_stage

    download_url = '"https://zenodo.org/records/${PM2S_MODEL_RECORD}/files/${model}?download=1"'
    download = pm2s_stage.index(download_url)
    verification = pm2s_stage.index("sha256sum --check -;", download)
    assert verification > download
