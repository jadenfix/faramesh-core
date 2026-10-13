#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

bin="$work_dir/faramesh"
base="$work_dir/release"
outside="$work_dir/outside"
mkdir -p "$base" "$outside"

echo "[build] compiling current Faramesh source"
(
  cd "$repo_root"
  go build -trimpath -o "$bin" ./cmd/faramesh
)

printf 'agent demo { default deny }\n' >"$base/policy.fpl"
cp "$base/policy.fpl" "$outside/policy.fpl"

echo "[1/3] generate and verify a confined release manifest"
"$bin" verify manifest-generate \
  --base-dir "$base" \
  --output "$base/manifest.json" \
  "$base/policy.fpl"
"$bin" verify manifest "$base/manifest.json" --base-dir "$base"

echo "[2/3] detect content tampering"
printf 'agent demo { default permit }\n' >"$base/policy.fpl"
if "$bin" verify manifest "$base/manifest.json" --base-dir "$base" >/dev/null 2>&1; then
  echo "ERROR: modified artifact passed verification" >&2
  exit 1
fi
echo "DENY modified artifact: digest mismatch"

echo "[3/3] reject a same-content symlink escaping --base-dir"
rm "$base/policy.fpl"
ln -s "$outside/policy.fpl" "$base/policy.fpl"
if "$bin" verify manifest "$base/manifest.json" --base-dir "$base" >/dev/null 2>&1; then
  echo "ERROR: escaping symlink passed verification" >&2
  exit 1
fi
echo "DENY escaping symlink: resolved path escapes base-dir"

echo "PASS artifact manifest containment"
