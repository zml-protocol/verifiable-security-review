"""Distractor generation for RD truth items (PREREGISTRATION.md §15.1 item 4). DRAFT — pending
Codex review; run only after the fixture queue is frozen and truth items exist.

Three mechanical rules produce distractors from an author item:

1. **near-move** — relocate a present anchor to a nearby location (§10.4 style);
2. **kind swap** — rebuild a qualifier under a different ``kind``;
3. **state flip** — flip present/absent on exactly one revision.

Anchors and absent-contexts live in real code, so this module never fabricates them: the caller
supplies ``relocate(anchor)``, ``context_for(anchor)`` and ``present_for(context)`` callbacks (the
frozen anchor machinery at fixture time). The module does the bookkeeping — walking the per-revision
slots, validating structure, minting unique ids and marking ``author_expected: NOT_REQUIRED`` —
and returns no distractor where a callback cannot produce a valid anchor.

    uv run python experiments/rd/truth/distractors.py --self-test
"""

from __future__ import annotations

import argparse
import copy

import vocabulary

SLOT_KEYS = ("revision_A", "revision_B")


def is_slot(value) -> bool:
    return isinstance(value, dict) and bool(set(value) & set(SLOT_KEYS))


def slots(item: dict):
    for key, value in item.items():
        if is_slot(value):
            yield key, value


def flip_state(item: dict, revision: str, context_for=None, present_for=None):
    """Flip ``present`` <-> ``absent`` on one revision, using the caller's callbacks."""
    out = copy.deepcopy(item)
    for _, slot in slots(out):
        realization = slot.get(revision) or {}
        state = realization.get("state")
        if state == "present":
            if context_for is None:
                return None
            context = context_for(realization.get("anchor"))
            if context is None:
                return None
            slot[revision] = {"state": "absent", "context": context}
        elif state == "absent":
            if present_for is None:
                return None
            anchor = present_for(realization.get("context"))
            if anchor is None:
                return None
            slot[revision] = {"state": "present", "anchor": anchor}
        else:
            return None
    return out


def relocate(item: dict, relocate):
    """Apply a near-move to every present anchor; fail closed if any relocation fails."""
    out = copy.deepcopy(item)
    moved = False
    for _, slot in slots(out):
        for revision in SLOT_KEYS:
            realization = slot.get(revision) or {}
            if realization.get("state") == "present":
                anchor = relocate(realization.get("anchor"))
                if anchor is None:
                    return None
                realization["anchor"] = anchor
                moved = True
    return out if moved else None


def swap_kind(item: dict, new_kind: str, rebuild, allowed: tuple[str, ...]):
    """Swap a qualifier's kind through the caller's rebuild(item, new_kind) -> item|None.
    Only kinds still in the frozen vocabulary may be a distractor target (§15.1/§15.4)."""
    if item.get("kind") not in allowed or new_kind not in allowed:
        return None
    if rebuild is None:
        return None
    out = rebuild(copy.deepcopy(item), new_kind)
    if not isinstance(out, dict) or out.get("kind") != new_kind:
        return None
    return out


def generate_with_ledger(item: dict, *, relocator=None, context_for=None, present_for=None,
                         rebuild=None, kinds: tuple[str, ...] | None = None) -> tuple[list[dict], list[dict]]:
    """Distractors for one author item plus the per-rule ledger.

    Every (item, rule) is recorded as ``generated`` or ``not_applicable`` with a reason, so a
    report can show why a requirement class carried fewer distractors (Codex Q3). The allowed
    qualifier kinds come from the frozen vocabulary; ``transform`` cannot be a target.
    """
    allowed = kinds if kinds is not None else vocabulary.allowed_qualifier_kinds()
    item_kind = item.get("kind")
    if item_kind not in ("entry", "behavior") and item_kind not in allowed:
        # an unsupported author item does not enter RD scoring, so it gets no distractor challenge
        return [], [{"id": item.get("id"), "rule": "vocabulary", "status": "not_applicable",
                     "reason": f"kind {item_kind!r} is not admissible in the frozen truth vocabulary"}]
    out: list[dict] = []
    ledger: list[dict] = []

    def record(rule: str, produced: dict | None, reason: str = "") -> None:
        if produced is None:
            ledger.append({"id": item.get("id"), "rule": rule, "status": "not_applicable", "reason": reason})
        else:
            out.append(produced)
            ledger.append({"id": item.get("id"), "rule": rule, "status": "generated"})

    record("near-move", relocate(item, relocator) if relocator else None,
           "" if relocator else "no relocator callback supplied")
    for revision in SLOT_KEYS:
        record(f"state-flip:{revision}",
               flip_state(item, revision, context_for=context_for, present_for=present_for),
               "missing context_for/present_for callback or anchor unavailable")
    if item.get("kind") in allowed:
        for kind in allowed:
            if kind == item.get("kind"):
                continue
            record(f"kind-swap:{kind}", swap_kind(item, kind, rebuild, allowed),
                   "rebuild callback missing or required payload unavailable")

    for i, distractor in enumerate(out, 1):
        distractor["id"] = f"{item['id']}-d{i}"
        distractor["distractor"] = True
        distractor["author_expected"] = "NOT_REQUIRED"
    return out, ledger


def generate(item: dict, **kwargs) -> list[dict]:
    """Distractor list only; use :func:`generate_with_ledger` when the ledger matters."""
    return generate_with_ledger(item, **kwargs)[0]


def self_test() -> None:
    item = {
        "id": "req-1", "kind": "guard", "expected": "must_hold",
        "subject": {rev: {"state": "present", "anchor": {"file": "a", "start_line": n}}
                    for n, rev in enumerate(SLOT_KEYS, 1)},
        "predicate": {rev: {"state": "present", "anchor": {"file": "a", "start_line": n + 10}}
                      for n, rev in enumerate(SLOT_KEYS, 1)},
    }
    move = lambda a: {**a, "start_line": a["start_line"] + 1} if a else None
    ctx = lambda a: {"file": a["file"], "start_line": a["start_line"] + 2, "expression": "stmt"} if a else None
    present = lambda c: {"file": c["file"], "start_line": c["start_line"] + 3, "expression": "check"} if c else None

    def rebuild(it, kind):
        it["kind"] = kind
        if kind == "guard":
            it["expected"] = "must_hold"
        elif kind == "transform":
            return None  # transform is not in the frozen vocabulary
        elif kind == "config":
            it["expected_condition"] = {"op": "set"}
        else:
            return None  # dispatch_target needs fields we cannot invent
        return it

    out, ledger = generate_with_ledger(item, relocator=move, context_for=ctx,
                                       present_for=present, rebuild=rebuild)
    ids = [d["id"] for d in out]
    assert len(ids) == len(set(ids)) and len(ids) == 4, (ids, ledger)
    assert all(d["author_expected"] == "NOT_REQUIRED" and d.get("distractor") for d in out)
    assert all(d.get("kind") != "transform" for d in out)
    assert any(r["rule"] == "kind-swap:config" and r["status"] == "generated" for r in ledger)
    assert any(r["rule"] == "kind-swap:dispatch_target" and r["status"] == "not_applicable" for r in ledger)
    assert not any("transform" in r["rule"] for r in ledger)
    assert any(r["status"] == "not_applicable" and r["reason"] for r in ledger)
    flips = [d for d in out if d["subject"]["revision_A"]["state"] != item["subject"]["revision_A"]["state"]]
    assert flips, out
    assert flip_state(item, "revision_A") is None  # no callback -> refuse to fabricate

    unsupported = {"id": "u-1", "kind": "transform", "expected": "must_be_present",
                   "subject": {r: {"state": "present", "anchor": {"file": "x", "start_line": 1}}
                               for r in SLOT_KEYS}}
    out_u, ledger_u = generate_with_ledger(unsupported, relocator=move, context_for=ctx,
                                           present_for=present, rebuild=rebuild)
    assert out_u == [] and len(ledger_u) == 1, (out_u, ledger_u)
    assert ledger_u[0]["rule"] == "vocabulary" and ledger_u[0]["status"] == "not_applicable", ledger_u
    print(f"distractors self-test OK ({len(out)} distractors, "
          f"{sum(1 for r in ledger if r['status'] == 'not_applicable')} not applicable)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    ap.error("nothing to do without fixture items; use --self-test")


if __name__ == "__main__":
    main()
