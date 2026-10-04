"""Frozen truth-vocabulary access for the truth tools (PREREGISTRATION.md §15.1, §15.4).

Reads ``results/rd-vocabulary.json`` and exposes only what the truth phase needs:

- ``allowed_qualifier_kinds()``: qualifier kinds whose frozen outcome is ADMISSIBLE. Derived from
  the table, never hardcoded: a kind that exited the vocabulary (``transform``) is absent here.
- ``is_admissible(kind)``: entry, behavior and the admissible qualifier kinds.

Fail-loud when the file is missing or the conformance gate is not READY. ``provider_support`` is
deliberately not exposed: provider capability must not decide what a requirement is.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VOCABULARY = ROOT / "results" / "rd-vocabulary.json"

# The §15.4 qualifier universe, before adjudication can remove members.
QUALIFIER_UNIVERSE = ("guard", "config", "dispatch_target", "transform")
REQUIREMENT_FIXED = ("entry", "behavior")


def _table() -> dict:
    if not VOCABULARY.exists():
        raise SystemExit(f"missing frozen vocabulary: {VOCABULARY}")
    doc = json.loads(VOCABULARY.read_text())
    if doc.get("gate_status") != "READY":
        raise SystemExit(f"conformance gate is {doc.get('gate_status')!r}: truth tools refuse to run")
    table = doc.get("truth_vocabulary") or {}
    if not isinstance(table, dict):
        raise SystemExit("truth_vocabulary is not a mapping")
    return table


def allowed_qualifier_kinds() -> tuple[str, ...]:
    table = _table()
    return tuple(kind for kind in QUALIFIER_UNIVERSE
                 if (table.get(kind) or {}).get("outcome") == "ADMISSIBLE")


def is_admissible(kind: str) -> bool:
    return kind in REQUIREMENT_FIXED or kind in allowed_qualifier_kinds()


if __name__ == "__main__":
    print({"allowed_qualifier_kinds": list(allowed_qualifier_kinds()),
           "entry_behavior": list(REQUIREMENT_FIXED)})
