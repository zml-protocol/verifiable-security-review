"""RD v3-only schemas layered over the immutable RD v2 A/B contract."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

import schema as v2_schema  # noqa: E402

ATTRIBUTION_STATUSES = v2_schema.ATTRIBUTION_STATUSES
REVISIONS = v2_schema.REVISIONS
_CWE = re.compile(r"^CWE-[1-9][0-9]*$")


class V3SchemaError(v2_schema.SchemaError):
    pass


def _rationale(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise V3SchemaError("rationale must be a string or null")
    return value.strip() or None


def effect_attribution(value: Any) -> dict:
    """Validate C1 without exposing or accepting a taxonomy label."""
    if not isinstance(value, dict):
        raise V3SchemaError("C1 conclusion must be an object")
    allowed = {*REVISIONS, "rationale"}
    if set(value) not in (allowed, allowed - {"rationale"}):
        raise V3SchemaError(f"C1 conclusion must have exactly {sorted(allowed)} (rationale optional)")
    out = {}
    for revision in REVISIONS:
        status = value.get(revision)
        if status not in ATTRIBUTION_STATUSES:
            raise V3SchemaError(
                f"C1 {revision} must be one of {list(ATTRIBUTION_STATUSES)}"
            )
        out[revision] = status
    out["rationale"] = _rationale(value.get("rationale"))
    return out


def cwe_taxonomy(value: Any) -> dict:
    """Validate the mutually exclusive C2 ranked-list / abstention forms."""
    if not isinstance(value, dict):
        raise V3SchemaError("C2 taxonomy must be an object")
    rationale = _rationale(value.get("rationale"))
    if "ranked_cwes" in value:
        if set(value) not in ({"ranked_cwes"}, {"ranked_cwes", "rationale"}):
            raise V3SchemaError("ranked C2 output has only ranked_cwes and optional rationale")
        ranked = value["ranked_cwes"]
        if not isinstance(ranked, list) or not 1 <= len(ranked) <= 3:
            raise V3SchemaError("ranked_cwes must contain one to three CWE ids")
        if any(not isinstance(item, str) or not _CWE.fullmatch(item) for item in ranked):
            raise V3SchemaError("each ranked CWE id must have canonical form CWE-<positive integer>")
        if len(set(ranked)) != len(ranked):
            raise V3SchemaError("ranked_cwes must not contain duplicates")
        return {"ranked_cwes": copy.deepcopy(ranked), "rationale": rationale}
    if set(value) not in ({"result"}, {"result", "rationale"}) \
            or value.get("result") != "NO_CONFIDENT_CWE":
        raise V3SchemaError(
            "C2 must contain either ranked_cwes or result=NO_CONFIDENT_CWE, plus optional rationale"
        )
    return {"result": "NO_CONFIDENT_CWE", "rationale": rationale}


canonical_bytes = v2_schema.canonical_bytes
seal = v2_schema.seal
sealed = v2_schema.sealed
verify_seal = v2_schema.verify_seal
