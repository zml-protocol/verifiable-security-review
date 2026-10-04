"""Canonical schemas and seals for the RD A -> B -> C protocol.

This module is deliberately fixture-free.  It validates only the frozen public
contract and delegates anchor resolution to the caller, which is the only part
that needs repository source.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from typing import Any

REVISIONS = ("revision_A", "revision_B")
ANCHOR_KEYS = frozenset({"file", "start_line", "end_line", "expression"})
QUALIFIER_KINDS = ("guard", "config", "dispatch_target")
ATTRIBUTION_STATUSES = ("SUPPORTED", "NOT_SUPPORTED", "INDETERMINATE")
HOP_KEYS = frozenset({"revision", "relation", "from", "to"})


class SchemaError(ValueError):
    """A public protocol object is invalid."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def seal(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sealed(value: dict, *, field: str = "seal") -> dict:
    out = copy.deepcopy(value)
    if field in out:
        raise SchemaError(f"reserved field {field!r} is not allowed")
    out[field] = seal(out)
    return out


def verify_seal(value: dict, *, field: str = "seal") -> str:
    if not isinstance(value, dict) or not isinstance(value.get(field), str):
        raise SchemaError(f"missing {field}")
    body = {k: copy.deepcopy(v) for k, v in value.items() if k != field}
    got = seal(body)
    if got != value[field]:
        raise SchemaError(f"{field} mismatch")
    return got


def _exact(value: Any, keys: set[str] | frozenset[str], what: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(keys):
        got = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise SchemaError(f"{what} must have exactly {sorted(keys)}; got {got}")
    return value


def anchor(value: Any, what: str = "anchor") -> dict:
    a = _exact(value, ANCHOR_KEYS, what)
    if not isinstance(a["file"], str) or not a["file"].strip():
        raise SchemaError(f"{what}.file must be a non-empty string")
    if a["file"].startswith("/") or ".." in a["file"].split("/") or "\x00" in a["file"]:
        raise SchemaError(f"{what}.file must be repository-relative")
    if not isinstance(a["start_line"], int) or not isinstance(a["end_line"], int):
        raise SchemaError(f"{what} line numbers must be integers")
    if not 1 <= a["start_line"] <= a["end_line"]:
        raise SchemaError(f"{what} needs 1 <= start_line <= end_line")
    if not isinstance(a["expression"], str) or not a["expression"].strip():
        raise SchemaError(f"{what}.expression must be non-empty")
    return copy.deepcopy(a)


def realization(value: Any, what: str) -> dict:
    if not isinstance(value, dict):
        raise SchemaError(f"{what} must be an object")
    state = value.get("state")
    if state == "present":
        _exact(value, {"state", "anchor"}, what)
        return {"state": state, "anchor": anchor(value["anchor"], f"{what}.anchor")}
    if state == "absent":
        _exact(value, {"state", "context"}, what)
        return {"state": state, "context": anchor(value["context"], f"{what}.context")}
    raise SchemaError(f"{what}.state must be present or absent")


def slot(value: Any, what: str) -> dict:
    s = _exact(value, set(REVISIONS), what)
    out = {rev: realization(s[rev], f"{what}.{rev}") for rev in REVISIONS}
    if all(r["state"] == "absent" for r in out.values()):
        raise SchemaError(f"{what} cannot be absent in both revisions")
    return out


def _note(value: Any, what: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{what} must be a non-empty string")
    return value.strip()


def qualifier(value: Any, index: int) -> dict:
    what = f"required_qualifiers[{index}]"
    if not isinstance(value, dict):
        raise SchemaError(f"{what} must be an object")
    kind = value.get("kind")
    if kind == "UNSUPPORTED_REQUIREMENT_TYPE":
        _exact(value, {"kind", "note"}, what)
        return {"kind": kind, "note": _note(value["note"], f"{what}.note", required=True)}
    if kind == "guard":
        allowed = {"kind", "expected", "subject", "predicate", "note"}
        if set(value) not in (allowed, allowed - {"note"}):
            raise SchemaError(f"{what} has invalid fields for guard")
        if value.get("expected") not in ("must_hold", "must_not_hold"):
            raise SchemaError(f"{what}.expected must be must_hold or must_not_hold")
        out = {"kind": kind, "expected": value["expected"],
               "subject": slot(value.get("subject"), f"{what}.subject"),
               "predicate": slot(value.get("predicate"), f"{what}.predicate")}
    elif kind == "config":
        allowed = {"kind", "expected_condition", "subject", "config", "note"}
        if set(value) not in (allowed, allowed - {"note"}):
            raise SchemaError(f"{what} has invalid fields for config")
        cond = value.get("expected_condition")
        if not isinstance(cond, dict) or cond.get("op") not in ("equals", "not_equals", "set", "unset"):
            raise SchemaError(f"{what}.expected_condition has an invalid op")
        needed = {"op", "value"} if cond["op"] in ("equals", "not_equals") else {"op"}
        _exact(cond, needed, f"{what}.expected_condition")
        if "value" in cond and (not isinstance(cond["value"], str) or not cond["value"].strip()):
            raise SchemaError(f"{what}.expected_condition.value must be a non-empty literal")
        out = {"kind": kind, "expected_condition": copy.deepcopy(cond),
               "subject": slot(value.get("subject"), f"{what}.subject"),
               "config": slot(value.get("config"), f"{what}.config")}
    elif kind == "dispatch_target":
        allowed = {"kind", "call", "target", "note"}
        if set(value) not in (allowed, allowed - {"note"}):
            raise SchemaError(f"{what} has invalid fields for dispatch_target")
        out = {"kind": kind, "call": slot(value.get("call"), f"{what}.call"),
               "target": slot(value.get("target"), f"{what}.target")}
    else:
        raise SchemaError(
            f"{what}.kind must be one of {[*QUALIFIER_KINDS, 'UNSUPPORTED_REQUIREMENT_TYPE']}"
        )
    if "note" in value:
        out["note"] = _note(value["note"], f"{what}.note")
    return out


def requirements(value: Any, resolve_anchor: Callable[[str, dict], Any]) -> dict:
    """Validate and resolve all anchors, returning the canonical public A payload."""
    allowed = {"entry", "behavior", "required_qualifiers", "rationale"}
    if not isinstance(value, dict) or set(value) not in (allowed, allowed - {"rationale"}):
        raise SchemaError(f"requirements must have {sorted(allowed)} (rationale is optional)")
    qs = value.get("required_qualifiers")
    if not isinstance(qs, list) or len(qs) > 6:
        raise SchemaError("required_qualifiers must be a list with at most 6 items")
    out = {
        "entry": slot(value.get("entry"), "entry"),
        "behavior": slot(value.get("behavior"), "behavior"),
        "required_qualifiers": [qualifier(q, i) for i, q in enumerate(qs)],
    }
    if sum(q["kind"] == "UNSUPPORTED_REQUIREMENT_TYPE" for q in out["required_qualifiers"]) > 2:
        raise SchemaError("at most two UNSUPPORTED_REQUIREMENT_TYPE proposals are allowed")
    if "rationale" in value:
        out["rationale"] = _note(value["rationale"], "rationale")

    def check_slot(s: dict) -> None:
        for rev, r in s.items():
            key = "anchor" if r["state"] == "present" else "context"
            resolve_anchor(rev, r[key])

    check_slot(out["entry"])
    check_slot(out["behavior"])
    for q in out["required_qualifiers"]:
        for name in (set(q) & {"subject", "predicate", "config", "call", "target"}):
            check_slot(q[name])
    return out


def hop(value: Any, relations: set[str]) -> dict:
    h = _exact(value, HOP_KEYS, "hop")
    if h["revision"] not in REVISIONS:
        raise SchemaError(f"hop.revision must be one of {list(REVISIONS)}")
    if h["relation"] not in {*relations, "unsupported"}:
        raise SchemaError(f"hop.relation must be one of {sorted([*relations, 'unsupported'])}")
    return {"revision": h["revision"], "relation": h["relation"],
            "from": anchor(h["from"], "hop.from"), "to": anchor(h["to"], "hop.to")}


def conclusion(value: Any) -> dict:
    allowed = {"revision_A", "revision_B", "rationale"}
    if not isinstance(value, dict) or set(value) not in (allowed, allowed - {"rationale"}):
        raise SchemaError(f"conclusion must have {sorted(allowed)} (rationale is optional)")
    out = {}
    for rev in REVISIONS:
        if value.get(rev) not in ATTRIBUTION_STATUSES:
            raise SchemaError(f"{rev} must be one of {list(ATTRIBUTION_STATUSES)}")
        out[rev] = value[rev]
    if "rationale" in value:
        out["rationale"] = _note(value["rationale"], "rationale")
    return out
