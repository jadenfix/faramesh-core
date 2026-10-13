#!/usr/bin/env python3
"""Verify source provenance, bytes, and decodeability of the artifact demo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "artifact-manifest"


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    capture = json.loads((OUT / "capture.json").read_text(encoding="utf-8"))
    source = json.loads((OUT / "source-manifest.json").read_text(encoding="utf-8"))
    commit = source["captured_source_commit"]
    assert capture["captured_source_commit"] == commit
    assert run("git", "rev-parse", f"{commit}^{{tree}}") == source["captured_source_tree"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
    for path, blob in source["runtime_inputs"].items():
        assert run("git", "rev-parse", f"HEAD:{path}") == blob, f"runtime source drift: {path}"

    assert sha256(OUT / "receipt.txt") == capture["workflow_output_sha256"]
    for name, expected in capture["artifacts"].items():
        path = OUT / name
        assert path.stat().st_size == expected["bytes"], f"size mismatch: {name}"
        assert sha256(path) == expected["sha256"], f"digest mismatch: {name}"

    gif_frames = int(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(OUT / "artifact-manifest.gif")))
    mp4_probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,nb_read_frames", "-of", "json", str(OUT / "artifact-manifest.mp4")))
    stream = mp4_probe["streams"][0]
    assert gif_frames == capture["video"]["frames"]
    assert stream["codec_name"] == "h264"
    assert int(stream["width"]) == capture["video"]["width"]
    assert int(stream["height"]) == capture["video"]["height"]
    assert int(stream["nb_read_frames"]) == capture["video"]["frames"]
    print(f"PASS source {commit[:12]} + {len(source['runtime_inputs'])} inputs + {gif_frames} decoded frames")


if __name__ == "__main__":
    main()
