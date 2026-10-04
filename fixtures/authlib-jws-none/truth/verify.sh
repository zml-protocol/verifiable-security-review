#!/usr/bin/env bash
# Install authlib at the case's base and head commits into throwaway venvs
# and run poc.py against each. Output is recorded in result.json.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$here/../../../.cache/repos/authlib.git"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
declare -A commits=([base]=21f7f50820f3906cebad308b35c816abf746ec3d [head]=a61c2acb807496e67f32051b5f1b1d5ccf8f0a75)
out="{"
for side in base head; do
  src="$work/src-$side"; mkdir -p "$src"
  git -C "$repo" archive "${commits[$side]}" | tar -x -C "$src"
  uv venv -q --python 3.12 "$work/venv-$side"
  VIRTUAL_ENV="$work/venv-$side" uv pip install -q "$src" "cryptography==45.0.7"
  py="$work/venv-$side/bin/python"
  versions=$("$py" -c 'import sys, authlib, cryptography; print(f"python {sys.version.split()[0]}, authlib {authlib.__version__}, cryptography {cryptography.__version__}")')
  result=$("$py" "$here/poc.py")
  out+="\"$side\": {\"commit\": \"${commits[$side]}\", \"env\": \"$versions\", \"probes\": $result},"
done
printf '%s' "${out%,}}" | python3 -m json.tool | tee "$here/result.json"
