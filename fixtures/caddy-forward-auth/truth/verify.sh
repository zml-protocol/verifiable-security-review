#!/usr/bin/env bash
# Build Caddy at the base and head commits, run each against the same stub
# auth service and echo upstream, and record what the upstream receives.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../../_truth/goenv.sh"
repo="$here/../../../.cache/repos/caddy.git"
work="$(mktemp -d)"
cleanup() { kill $(jobs -p) 2>/dev/null || true; rm -rf "$work"; }
trap cleanup EXIT
declare -A commits=([base]=00f948c6056f6968b07e2b92d537c0a61559e2ed [head]=05cfb121ec3f214c0e45206c188f34bad4d4eb8c)

python3 "$here/stubs.py" 18081 18082 > "$work/stubs.log" 2>&1 &
until grep -q ready "$work/stubs.log"; do sleep 0.2; done

probe() {  # probe <path> [client X-User-ID]
  local args=(-s "http://127.0.0.1:18080$1")
  [ $# -ge 2 ] && args+=(-H "X-User-ID: $2")
  curl "${args[@]}"
}

out="{\"toolchain\": \"$(go version)\", \"env\": \"GOTOOLCHAIN=$GOTOOLCHAIN GOFLAGS=$GOFLAGS CGO_ENABLED=$CGO_ENABLED\","
for side in base head; do
  src="$work/$side"; mkdir -p "$src"
  git -C "$repo" archive "${commits[$side]}" | tar -x -C "$src"
  mkdir -p "$src/cmd/truthprobe" && cp "$here/probe_main.go" "$src/cmd/truthprobe/main.go"
  (cd "$src" && go build -o "$work/caddy-$side" ./cmd/truthprobe)
  "$work/caddy-$side" run --config "$here/Caddyfile" --adapter caddyfile > "$work/caddy-$side.log" 2>&1 &
  pid=$!
  until curl -s -o /dev/null "http://127.0.0.1:18080/"; do sleep 0.2; done
  r1=$(probe /no-id admin)
  r2=$(probe /with-id admin)
  r3=$(probe /no-id)
  kill $pid; wait $pid 2>/dev/null || true
  out+="\"$side\": {\"commit\": \"${commits[$side]}\", \"version\": \"$("$work/caddy-$side" version | head -1)\","
  out+="\"P1_auth_omits_header_client_sends_admin\": $r1,"
  out+="\"P2_auth_returns_alice_client_sends_admin\": $r2,"
  out+="\"P3_auth_omits_header_client_sends_none\": $r3},"
done
printf '%s' "${out%,}}" | python3 -m json.tool | tee "$here/result.json"
