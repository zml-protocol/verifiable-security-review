"""Run validity (PREREGISTRATION.md §1.2): which failed runs may be rerun.

Only infrastructure failures are INFRA_INVALID and eligible for a rerun.
Everything the agent does to itself (budget or turn limits, timeouts,
refusals, never calling finish) is a VALID run that counts as it stands.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

INFRA_INVALID = "INFRA_INVALID"
VALID = "VALID"
MAX_ATTEMPTS = 3  # the original attempt plus two reruns

_API_ERROR = re.compile(
    r"API Error|overloaded|rate.?limit|\b5\d\d\b|ECONNRESET|ETIMEDOUT|Connection error|network",
    re.IGNORECASE,
)
# The CLI reports an exhausted subscription as subtype "success" with is_error set,
# e.g. "You've hit your weekly limit · resets Oct 2, 10pm (America/New_York)".
_USAGE_LIMIT = re.compile(r"hit your .*limit|usage limit|weekly limit|limit reached", re.IGNORECASE)


def result_text(result: dict) -> str:
    return " ".join(map(str, result.get("errors") or [])) + " " + str(result.get("result") or "")


def agent_events(run_dir: Path) -> list[dict]:
    path = run_dir / "agent.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def classify(run_dir: Path) -> tuple[str, str]:
    """Return (validity, reason) for a run the runner has already attempted."""
    events = agent_events(run_dir)
    if not (run_dir / "state.json").exists():
        return INFRA_INVALID, "server_not_started"
    if not any(e.get("type") == "system" and e.get("subtype") == "init" for e in events):
        return INFRA_INVALID, "agent_not_started"
    if any(
        e.get("type") == "assistant" and e["message"].get("stop_reason") == "refusal"
        for e in events
    ):
        return VALID, "refusal"
    results = [e for e in events if e.get("type") == "result"]
    if not results:
        meta_path = run_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        transcript = run_dir / "transcript.jsonl"
        worked = transcript.exists() and transcript.read_text().strip()
        if meta.get("exit") == "timeout" and worked:
            return VALID, "timeout"
        return INFRA_INVALID, "agent_crashed" if worked else "agent_stalled"
    result = results[-1]
    subtype = result.get("subtype", "")
    if result.get("is_error") and _USAGE_LIMIT.search(result_text(result)):
        return INFRA_INVALID, "usage_limit"
    if subtype == "success" and not result.get("is_error"):
        return VALID, "completed"
    if subtype.startswith("error_max_"):
        return VALID, subtype
    if _API_ERROR.search(result_text(result)):
        return INFRA_INVALID, "api_error"
    return VALID, subtype or "unknown_error"


def served_models(run_dir: Path) -> list[str]:
    """Model identifiers exactly as the API reported them."""
    models = set()
    for e in agent_events(run_dir):
        if e.get("type") == "system" and e.get("subtype") == "init" and e.get("model"):
            models.add(e["model"])
        if e.get("type") == "assistant" and e["message"].get("model"):
            models.add(e["message"]["model"])
    return sorted(models)
