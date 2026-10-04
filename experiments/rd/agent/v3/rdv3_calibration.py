"""Render the public, non-evaluation A calibration examples for one task language."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "a-development.yaml"


@lru_cache(maxsize=1)
def _cases() -> tuple[dict, ...]:
    doc = yaml.safe_load(CORPUS.read_text())
    if doc.get("schema") != "rd-v3-a-development/v1" or len(doc.get("cases") or []) != 10:
        raise RuntimeError("frozen A development corpus is invalid")
    return tuple(doc["cases"])


def examples(language: str) -> list[dict]:
    """Return exactly one frozen worked example per calibration cell for `language`."""
    rows = [case for case in _cases() if case.get("language") == language]
    if len(rows) != 5 or len({case["cell"] for case in rows}) != 5:
        raise RuntimeError(f"A development corpus does not cover five {language} cells")
    return [{"cell": case["cell"], "effect_claim": case["effect_claim"],
             "files": copy.deepcopy(case["files"]),
             "correct_entry": copy.deepcopy(case["expected"]["entry"]),
             "correct_behavior": copy.deepcopy(case["expected"]["behavior"])}
            for case in rows]
