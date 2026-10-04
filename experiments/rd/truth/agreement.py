"""Three-way agreement and completeness check for RD truth items (PREREGISTRATION.md §15.1 item 5).
DRAFT — pending Codex review; run only after the fixture queue is frozen.

Inputs (YAML):

author.yaml
    fixture: <id>
    items:
      - id: <str>
        author_expected: REQUIRED | NOT_REQUIRED   # default REQUIRED (distractors use NOT_REQUIRED)
        <kind-specific fields: entry/behavior are slots; qualifiers carry kind, semantic fields
         and anchor slots per §15.4; note is ignored for identity>

judge-a.yaml / judge-b.yaml
    labels: {<item id>: REQUIRED | NOT_REQUIRED | INDETERMINATE}
    missing: [<requirement item, §15.4 shape>]    # optional; only structural fields matter

Outputs (YAML): admissible items, indeterminate items, distractor conflicts, one- and two-sided
missing items, ambiguity burden, and whether the fixture is INCOMPLETE_TRUTH_SPEC.

Anchor identity is the single frozen matcher the scorer uses (``matcher.node_identity``, the
canonical syntax-node identity). Production binds to it directly and fails loud on a provenance/hash
mismatch; a caller may not substitute an arbitrary ``module:function`` (``--anchor-matcher`` is
accepted only if it equals the frozen spec). The exact tuple
``(file, start_line, end_line, expression)`` survives only as ``exact_identity`` inside
``--self-test``; it is not a production fallback.

    uv run python experiments/rd/truth/agreement.py author.yaml judge-a.yaml judge-b.yaml --out decision.yaml
    uv run python experiments/rd/truth/agreement.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import vocabulary

LABELS = ("REQUIRED", "NOT_REQUIRED", "INDETERMINATE")
SLOT_KEYS = ("revision_A", "revision_B")
# identity is computed from the structured, scored fields; note is not scored (§15.4)
UNSCORED = {"note", "author_expected", "id", "distractor", "fixture", "rationale"}


def exact_identity(anchor) -> tuple | None:
    """Diagnostic stand-in for the frozen matcher; self-test only, never production."""
    if not isinstance(anchor, dict):
        return None
    return (anchor.get("file"), anchor.get("start_line"), anchor.get("end_line"),
            anchor.get("expression"))


def slot_key(slot, anchor_identity) -> tuple:
    out = []
    for rev in SLOT_KEYS:
        realization = (slot or {}).get(rev) or {}
        state = realization.get("state")
        if state == "present":
            out.append((rev, "present", anchor_identity(realization.get("anchor"))))
        elif state == "absent":
            out.append((rev, "absent", anchor_identity(realization.get("context"))))
        else:
            out.append((rev, state))
    return tuple(out)


def item_identity(item: dict, anchor_identity) -> tuple:
    """Full requirement identity: kind, scored semantic fields, every anchor slot's state and
    anchor per revision (§15.1 item 5)."""
    fields = []
    for key, value in sorted(item.items()):
        if key in UNSCORED:
            continue
        if isinstance(value, dict) and set(value) & set(SLOT_KEYS):
            fields.append((key, slot_key(value, anchor_identity)))
        elif isinstance(value, (str, int, float, bool)) or value is None:
            fields.append((key, value))
        else:
            fields.append((key, json.dumps(value, sort_keys=True)))
    return tuple(fields)


def _index(items) -> dict:
    return {it["id"]: it for it in items or [] if isinstance(it, dict) and it.get("id")}


def check(author: dict, judge_a: dict, judge_b: dict, anchor_identity=None) -> dict:
    if anchor_identity is None:
        raise RuntimeError(
            "no frozen anchor_identity supplied: the production equivalence rule is the same frozen "
            "matcher the scorer uses. Refusing to fall back to exact tuples; pass the matcher "
            "callable explicitly, or use --self-test for the diagnostic path."
        )
    items = _index(author.get("items"))
    labels_a = judge_a.get("labels") or {}
    labels_b = judge_b.get("labels") or {}
    admissible, indeterminate, distractor_conflicts, distractors_rejected, missing_labels = [], [], [], [], []

    # Author items are classified against the frozen vocabulary before any agreement logic:
    # a kind that left the vocabulary (transform) or is unknown never reaches `admissible`,
    # regardless of what the adjudicators say. It is reported as a vocabulary blind spot.
    allowed_kinds = set(vocabulary.allowed_qualifier_kinds())
    author_blind_spots = []
    for item_id, item in items.items():
        kind = item.get("kind")
        if kind not in ("entry", "behavior") and kind not in allowed_kinds:
            author_blind_spots.append({"id": item_id, "kind": kind})
    blind_ids = {x["id"] for x in author_blind_spots}

    for item_id, item in items.items():
        if item_id in blind_ids:
            continue
        expected = item.get("author_expected", "REQUIRED")
        a, b = labels_a.get(item_id), labels_b.get(item_id)
        if a not in LABELS or b not in LABELS:
            missing_labels.append(item_id)
            if expected == "REQUIRED":
                indeterminate.append({"id": item_id, "a": a, "b": b, "reason": "missing label"})
            else:
                distractor_conflicts.append(item_id)
        elif expected == "REQUIRED":
            if a == b == "REQUIRED":
                admissible.append(item_id)
            else:
                indeterminate.append({"id": item_id, "a": a, "b": b, "reason": "three-way disagreement"})
        else:  # generated distractor: both adjudicators should reject it
            if a == b == "NOT_REQUIRED":
                distractors_rejected.append(item_id)
            else:
                distractor_conflicts.append(item_id)

    missing_a = judge_a.get("missing") or []
    missing_b = judge_b.get("missing") or []
    used_b, two_sided, one_sided = set(), [], []
    for ma in missing_a:
        match = next((i for i, mb in enumerate(missing_b)
                      if i not in used_b and item_identity(ma, anchor_identity) == item_identity(mb, anchor_identity)), None)
        if match is None:
            one_sided.append({"by": "A", "item": ma})
        else:
            used_b.add(match)
            two_sided.append(ma)
    for i, mb in enumerate(missing_b):
        if i not in used_b:
            one_sided.append({"by": "B", "item": mb})

    allowed_kinds = set(vocabulary.allowed_qualifier_kinds())
    fixture_incomplete = False
    qualifier_incomplete = False
    vocabulary_blind_spots = []
    for m in two_sided:
        kind = m.get("kind")
        if kind in ("entry", "behavior"):
            fixture_incomplete = True
        elif kind in allowed_kinds:
            qualifier_incomplete = True
        else:
            # e.g. a missing transform: the vocabulary no longer admits it, so this is an
            # unsupported requirement type / blind spot, not damage to qualifier truth (§15.7).
            vocabulary_blind_spots.append(m)

    return {
        "fixture": author.get("fixture"),
        "admissible": sorted(admissible),
        "indeterminate": indeterminate,
        "distractor_conflicts": sorted(set(distractor_conflicts)),
        "distractors_rejected": sorted(set(distractors_rejected)),
        "missing_labels": sorted(missing_labels),
        "missing": {
            "two_sided": two_sided,
            "one_sided": one_sided,
            "ambiguity_burden": len(one_sided),
        },
        "vocabulary_blind_spots": vocabulary_blind_spots,
        "author_vocabulary_blind_spots": author_blind_spots,
        "incomplete_truth_spec": fixture_incomplete,
        "qualifier_layer_inadmissible": qualifier_incomplete,
        "summary": {
            "items": len(items), "admissible": len(admissible), "indeterminate": len(indeterminate),
            "author_blind_spots": len(author_blind_spots),
            "two_sided_missing": len(two_sided), "one_sided_missing": len(one_sided),
        },
    }


def self_test() -> None:
    author = {"fixture": "t", "items": [
        {"id": "req-1", "kind": "guard", "expected": "must_hold",
         "subject": {r: {"state": "present", "anchor": {"file": "a.go", "start_line": i,
                                                        "end_line": i, "expression": "x"}} for i, r in enumerate(SLOT_KEYS, 1)}},
        {"id": "dist-1", "kind": "guard", "expected": "must_hold", "author_expected": "NOT_REQUIRED",
         "subject": {r: {"state": "present", "anchor": {"file": "b.go", "start_line": 9,
                                                        "end_line": 9, "expression": "y"}} for r in SLOT_KEYS}},
    ]}
    judge_a = {"labels": {"req-1": "REQUIRED", "dist-1": "NOT_REQUIRED"},
               "missing": [{"kind": "transform", "expected": "must_be_absent"}]}
    judge_b = {"labels": {"req-1": "REQUIRED", "dist-1": "REQUIRED"},   # distractor conflict
               "missing": [{"kind": "transform", "expected": "must_be_absent"}]}
    out = check(author, judge_a, judge_b, anchor_identity=exact_identity)
    assert out["admissible"] == ["req-1"], out
    assert out["distractor_conflicts"] == ["dist-1"], out
    # transform left the frozen vocabulary: a two-sided missing transform is a blind spot, not
    # qualifier incompleteness
    assert len(out["missing"]["two_sided"]) == 1 and out["missing"]["ambiguity_burden"] == 0, out
    assert len(out["vocabulary_blind_spots"]) == 1, out
    assert not out["qualifier_layer_inadmissible"] and not out["incomplete_truth_spec"], out

    # an admissible kind missing on both sides does invalidate the qualifier layer
    guard_missing = {"kind": "guard", "expected": "must_hold",
                     "subject": {"revision_A": {"state": "present", "anchor": {"file": "c.go", "start_line": 3}}}}
    judge_a_g = {"labels": {"req-1": "REQUIRED", "dist-1": "NOT_REQUIRED"}, "missing": [guard_missing]}
    judge_b_g = {"labels": {"req-1": "REQUIRED", "dist-1": "NOT_REQUIRED"}, "missing": [guard_missing]}
    out_g = check(author, judge_a_g, judge_b_g, anchor_identity=exact_identity)
    assert out_g["qualifier_layer_inadmissible"] and not out_g["vocabulary_blind_spots"], out_g

    judge_b2 = {"labels": {"req-1": "INDETERMINATE", "dist-1": "NOT_REQUIRED"}, "missing": []}
    out2 = check(author, judge_a_g, judge_b2, anchor_identity=exact_identity)
    assert [x["id"] for x in out2["indeterminate"]] == ["req-1"], out2
    assert out2["missing"]["ambiguity_burden"] == 1, out2

    # author-side unsupported kind: never admissible, even when both judges say REQUIRED
    author_t = {"fixture": "t2", "items": [
        {"id": "t-1", "kind": "transform", "expected": "must_be_present",
         "subject": {r: {"state": "present", "anchor": {"file": "d.go", "start_line": 1}}
                     for r in SLOT_KEYS}},
    ]}
    judges_t1 = {"labels": {"t-1": "REQUIRED"}, "missing": []}
    judges_t2 = {"labels": {"t-1": "REQUIRED"}, "missing": []}
    out_t = check(author_t, judges_t1, judges_t2, anchor_identity=exact_identity)
    assert out_t["admissible"] == [], out_t
    assert len(out_t["author_vocabulary_blind_spots"]) == 1, out_t
    assert out_t["missing_labels"] == [] and out_t["indeterminate"] == [], out_t

    # production refuses to run without the frozen matcher
    try:
        check(author, judge_a_g, judge_b2)
        raise AssertionError("production check must fail loud without anchor_identity")
    except RuntimeError:
        pass
    print("agreement self-test OK")


def load_matcher(spec: str | None):
    """Return the single frozen matcher after a provenance check. There is no arbitrary-spec path:
    a non-None spec must equal the frozen spec, and a changed matcher file fails loud."""
    import matcher

    try:
        return matcher.load_frozen_matcher(spec)
    except matcher.MatcherError as e:
        raise SystemExit(str(e))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("author", nargs="?")
    ap.add_argument("judge_a", nargs="?")
    ap.add_argument("judge_b", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--anchor-matcher", help="optional; must equal the frozen matcher spec "
                    "(matcher:node_identity). Production binds to the frozen matcher regardless.")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not (args.author and args.judge_a and args.judge_b):
        ap.error("author.yaml judge-a.yaml judge-b.yaml are required")
    load = lambda p: yaml.safe_load(Path(p).read_text()) or {}
    result = check(load(args.author), load(args.judge_a), load(args.judge_b),
                   anchor_identity=load_matcher(args.anchor_matcher))
    text = yaml.safe_dump(result, sort_keys=False)
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
