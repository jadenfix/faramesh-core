#!/usr/bin/env python3
"""Generate the source-pinned artifact-manifest CLI demo media."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "artifact-manifest"
SOURCE_COMMIT = "314173f0ff45dd421682037e78c1692c60202a6b"
WIDTH, HEIGHT = 1280, 720
FPS = 12


def run(*args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def frame(lines: list[tuple[str, str]], step: int, tick: int, total: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#07111f")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((38, 34, WIDTH - 38, HEIGHT - 34), 18, fill="#0d1b2a", outline="#29425f", width=2)
    d.rectangle((38, 34, WIDTH - 38, 94), fill="#13283c")
    for x, color in ((68, "#ff6b6b"), (98, "#ffd166"), (128, "#38d996")):
        d.ellipse((x - 8, 56 - 8, x + 8, 56 + 8), fill=color)
    d.text((174, 48), "faramesh  /  artifact integrity", font=font(22, True), fill="#dcecff")
    d.text((WIDTH - 220, 49), "ACTUAL CLI", font=font(18, True), fill="#55d6be")

    progress = max(1, int((WIDTH - 76) * (tick + 1) / total))
    d.rectangle((38, 92, 38 + progress, 95), fill="#55d6be")

    d.text((72, 122), "CONFINED RELEASE MANIFEST", font=font(30, True), fill="#ffffff")
    d.text((72, 169), "One valid artifact. Two adversarial mutations. Deterministic outcomes.", font=font(18), fill="#8faecb")

    y = 220
    for text, role in lines:
        colors = {
            "prompt": "#78b7ff",
            "ok": "#55d6be",
            "deny": "#ff7b86",
            "plain": "#d3dfeb",
        }
        prefix = {"prompt": "$ ", "ok": "✓ ", "deny": "✕ ", "plain": "  "}[role]
        d.text((80, y), prefix + text, font=font(19, role in {"ok", "deny"}), fill=colors[role])
        y += 43

    stages = ("BUILD", "VERIFY", "TAMPER", "CONTAIN")
    x0, y0, w, gap = 80, 641, 250, 18
    for idx, label in enumerate(stages):
        x = x0 + idx * (w + gap)
        active = idx <= step
        d.rounded_rectangle((x, y0, x + w, y0 + 34), 8, fill="#1b6f69" if active else "#1a2d40")
        d.text((x + 14, y0 + 7), label, font=font(15, True), fill="#eafffb" if active else "#6e8aa4")
    return img


def main() -> None:
    if run("git", "status", "--porcelain", "--", "cmd", "internal", "go.mod", "go.sum", "tests/artifact_manifest_containment.sh").strip():
        raise SystemExit("runtime inputs differ from captured source; commit or restore them first")
    if run("git", "rev-parse", f"{SOURCE_COMMIT}^{{tree}}").strip() != "f40393ed52cf7f197deb173b4a13b18cbfde3de5":
        raise SystemExit("captured source tree mismatch")

    env = os.environ.copy()
    transcript = run("bash", "tests/artifact_manifest_containment.sh", env=env)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "receipt.txt").write_text(transcript, encoding="utf-8")

    tracked = run("git", "ls-tree", "-r", "--name-only", SOURCE_COMMIT).splitlines()
    inputs = [
        path
        for path in tracked
        if path in {"go.mod", "go.sum", "tests/artifact_manifest_containment.sh"}
        or (path.endswith(".go") and path.startswith(("cmd/", "internal/")))
    ]
    source_manifest = {
        "schema": 1,
        "captured_source_commit": SOURCE_COMMIT,
        "captured_source_tree": run("git", "rev-parse", f"{SOURCE_COMMIT}^{{tree}}").strip(),
        "runtime_inputs": {
            path: run("git", "rev-parse", f"{SOURCE_COMMIT}:{path}").strip() for path in inputs
        },
    }
    (OUT / "source-manifest.json").write_text(
        json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    scenes = [
        ([
            ("go build -trimpath ./cmd/faramesh", "prompt"),
            ("current source compiled", "ok"),
        ], 0, 18),
        ([
            ("faramesh verify manifest-generate --base-dir release …", "prompt"),
            ("faramesh verify manifest manifest.json --base-dir release", "prompt"),
            ("all 1 artifacts match manifest", "ok"),
        ], 1, 24),
        ([
            ("modify policy.fpl after manifest generation", "prompt"),
            ("modified artifact: digest mismatch", "deny"),
            ("content tampering blocked before release", "ok"),
        ], 2, 24),
        ([
            ("replace policy.fpl with same-content symlink", "prompt"),
            ("symlink target resolves outside --base-dir", "plain"),
            ("escaping symlink: resolved path escapes base-dir", "deny"),
            ("artifact manifest containment passed", "ok"),
        ], 3, 30),
    ]
    frames: list[Image.Image] = []
    total_frames = sum(count for _, _, count in scenes)
    for lines, step, count in scenes:
        for _ in range(count):
            frames.append(frame(lines, step, len(frames), total_frames))

    poster = OUT / "artifact-manifest-poster.png"
    gif = OUT / "artifact-manifest.gif"
    mp4 = OUT / "artifact-manifest.mp4"
    frames[-1].save(poster, optimize=True)
    small = [im.resize((960, 540), Image.Resampling.LANCZOS) for im in frames]
    small[0].save(gif, save_all=True, append_images=small[1:], duration=1000 // FPS, loop=0, optimize=True)

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "frames"
        raw.mkdir()
        for idx, im in enumerate(frames):
            im.save(raw / f"{idx:04d}.png")
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(raw / "%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-metadata", "creation_time=1970-01-01T00:00:00Z", str(mp4),
        )

    receipt = {
        "schema": 1,
        "captured_source_commit": SOURCE_COMMIT,
        "captured_source_tree": source_manifest["captured_source_tree"],
        "command": "bash tests/artifact_manifest_containment.sh",
        "workflow_output_sha256": sha256(OUT / "receipt.txt"),
        "scope": "Provider-free local CLI artifact verification; no live service or performance claim.",
        "artifacts": {
            p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in (gif, mp4, poster)
        },
        "video": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frames": len(frames)},
    }
    (OUT / "capture.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
