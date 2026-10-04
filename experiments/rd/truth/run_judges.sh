#!/usr/bin/env bash
# Run the two independent RD truth adjudicators on a fixture's frozen judge-prompt.md, in isolation,
# and capture raw transcripts + extracted YAML. OPERATIONAL PLUMBING ONLY — it introduces no scoring
# or measurement rule; it is the automated form of the operator manually pasting the prompt into two
# fresh sessions. The author must NOT run this until the fixture's author truth is frozen (the
# self-review per ANCHOR-SELF-REVIEW.md is done and the bundle/judge-prompt.md is final).
#
# Judge A = gpt-6.1-sol via Codex CLI; Judge B = deepseek/deepseek-flash via OpenCode CLI.
#
# Isolation (per §15.1 fresh-session intent):
#  - Judge A: a FRESH CODEX_HOME holding only a copy of the ChatGPT-OAuth auth.json + an empty
#    config.toml -> no plugins, no hooks, no MCP; reasoning=medium; sandbox read-only; cwd = an empty
#    temp dir so it cannot read the repo/author files; final assistant message captured via -o.
#  - Judge B: a FRESH XDG_CONFIG_HOME (so the global opencode.jsonc + its MCP do NOT load); default
#    data dir retained only for the stored DeepSeek key; --standalone private server; cwd = empty.
#  - Each receives ONLY judge-prompt.md. Raw transcripts are saved for audit.
#
# CAVEAT (cannot be enforced from the CLI): Judge A runs on the ChatGPT account codex is logged into;
# that account's Memory and Custom Instructions MUST be OFF for the session to be independent. Confirm
# this out of band before trusting a run.
#
# Usage: run_judges.sh <fixture-dir>   (expects <fixture-dir>/judge-prompt.md)
set -euo pipefail
FIX="${1:?usage: run_judges.sh <fixture-dir>}"
PROMPT="$FIX/judge-prompt.md"
[ -f "$PROMPT" ] || { echo "missing $PROMPT" >&2; exit 1; }

# --- Judge A: Codex / gpt-6.1-sol -----------------------------------------------------------------
AHOME="$(mktemp -d)/codexhome"; mkdir -p "$AHOME"
cp "$HOME/.codex/auth.json" "$AHOME/" 2>/dev/null || { echo "no ~/.codex/auth.json (codex not logged in)" >&2; exit 1; }
printf '' > "$AHOME/config.toml"
ACWD="$(mktemp -d)"
echo "[Judge A] gpt-6.1-sol (fresh CODEX_HOME, read-only, empty cwd) ..." >&2
CODEX_HOME="$AHOME" codex exec -m gpt-6.1-sol -c model_reasoning_effort="medium" \
  -s read-only --skip-git-repo-check --cd "$ACWD" -o "$FIX/judge-a.yaml" - < "$PROMPT" \
  > "$FIX/judge-a.raw.txt" 2>&1 || { echo "[Judge A] codex exec failed; see judge-a.raw.txt" >&2; }

# --- Judge B: OpenCode / deepseek-flash -----------------------------------------------------------
BCFG="$(mktemp -d)/ocfg"; mkdir -p "$BCFG"
BCWD="$(mktemp -d)"
echo "[Judge B] deepseek-flash (fresh XDG_CONFIG_HOME, --standalone, empty cwd) ..." >&2
( cd "$BCWD" && XDG_CONFIG_HOME="$BCFG" opencode run --standalone -m deepseek/deepseek-flash \
    "$(cat "$PROMPT")" ) > "$FIX/judge-b.raw.txt" 2>&1 || { echo "[Judge B] opencode run failed; see judge-b.raw.txt" >&2; }
# Extract the YAML body from Judge B's transcript (strip the leading "> build · model" banner line).
awk 'f{print} /^labels:/{print; f=1}' "$FIX/judge-b.raw.txt" > "$FIX/judge-b.yaml" || true
[ -s "$FIX/judge-b.yaml" ] || cp "$FIX/judge-b.raw.txt" "$FIX/judge-b.yaml"

echo "done: $FIX/judge-a.yaml (codex -o), $FIX/judge-b.yaml (extracted); raw: judge-a.raw.txt, judge-b.raw.txt" >&2
