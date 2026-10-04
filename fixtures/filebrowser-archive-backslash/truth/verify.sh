#!/usr/bin/env bash
# Run truth_probe_test.go inside http/ at the base and head commits.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../../_truth/goenv.sh"
repo="$here/../../../.cache/repos/filebrowser.git"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
declare -A commits=([base]=0231b7ebdfbe77a6c54027d30c4856c3fd81ee4d [head]=847d08bdd135e5c3659f2e6dea2f0cd36617af9b)
out="{\"toolchain\": \"$(go version)\", \"env\": \"GOTOOLCHAIN=$GOTOOLCHAIN GOFLAGS=$GOFLAGS CGO_ENABLED=$CGO_ENABLED\","
for side in base head; do
  src="$work/$side"; mkdir -p "$src"
  git -C "$repo" archive "${commits[$side]}" | tar -x -C "$src"
  cp "$here/truth_probe_test.go" "$src/http/"
  log=$(cd "$src" && go test ./http -run '^TestTruthProbe$' -count=1 -v 2>&1) || { echo "$log" >&2; exit 1; }
  json=$(printf '%s\n' "$log" | sed -n '/TRUTH {/,/^        }$/p' | sed 's/^.*TRUTH //; s/^        //')
  out+="\"$side\": {\"commit\": \"${commits[$side]}\", \"probe\": $json},"
done
printf '%s' "${out%,}}" | python3 -m json.tool | tee "$here/result.json"
