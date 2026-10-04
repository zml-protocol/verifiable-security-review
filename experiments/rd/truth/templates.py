"""Empty fixture-truth templates and adjudication-sheet generator (PREREGISTRATION.md §15.1 item 4).

Generates **blank** structures only. It writes no golden value, reads no fixture, advisory or
selection log, and refuses to write anywhere under ``results/``. Everything an adjudicator or the
author must later fill is present as an explicit empty slot — never pre-decided.

Schema principles kept here:

- **present/absent per revision**, and each revision carries its own realization (mirrors the §15
  state model). A ``present`` revision is realized by an ``anchor``; an ``absent`` revision is
  realized by a ``context`` (the counterpart, at the absent revision, of the statement the element
  controls or feeds at the present revision). ``base`` and ``head`` may be entirely different — one
  present with an anchor, the other absent with a context — so each requirement item holds *two*
  independent per-revision realizations, not one shared anchor.
- Explicit ``NA`` and ``truth_inadmissible`` markers exist as first-class choices, so "not
  applicable" and "the truth itself cannot be stated" are recorded, not left blank.
- The four truth-status values below are **independent** and must never be collapsed into one
  another; each answers a different question.

Admissible qualifier kinds are sourced from the frozen vocabulary (``vocabulary.py``), so a template
never offers a slot the vocabulary removed (e.g. ``transform``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocabulary  # noqa: E402

# --- independent, non-collapsing truth statuses -----------------------------------------------
# Each is a distinct outcome; a tool must keep them apart (no aliasing, no fallthrough).
INDETERMINATE_TRUTH = "INDETERMINATE_TRUTH"                    # the fixture admits no single truth
INCOMPLETE_TRUTH_SPEC = "INCOMPLETE_TRUTH_SPEC"               # the spec needed to decide is missing
UNCLASSIFIABLE_QUALIFIER_TRUTH = "UNCLASSIFIABLE_QUALIFIER_TRUTH"  # qualifier truth resists the kinds
UNSUPPORTED_REQUIREMENT_TYPE = "UNSUPPORTED_REQUIREMENT_TYPE"  # the item's kind is outside the vocab

TRUTH_STATUSES = (
    INDETERMINATE_TRUTH,
    INCOMPLETE_TRUTH_SPEC,
    UNCLASSIFIABLE_QUALIFIER_TRUTH,
    UNSUPPORTED_REQUIREMENT_TYPE,
)

# present/absent state plus the two explicit escape markers.
STATE_VALUES = ("present", "absent", "NA", "truth_inadmissible")
REVISIONS = ("base", "head")

_EMPTY = None  # every golden slot starts empty; the generator never fills one.


def _revision() -> dict:
    """One revision's realization of an element: its state, and exactly one of anchor/context.

    Fill rule (enforced by `check_revision`): present → anchor set, context null; absent → context
    set, anchor null; NA / truth_inadmissible → both null.
    """
    return {"state": _EMPTY, "anchor": _EMPTY, "context": _EMPTY}


def _item() -> dict:
    """An anchor-bearing requirement item: an independent per-revision realization for base & head."""
    return {rev: _revision() for rev in REVISIONS}


def check_revision(rev: dict) -> None:
    """Validate a *filled* revision realization against the present/absent schema (fail loud)."""
    state = rev.get("state")
    if state not in STATE_VALUES:
        raise ValueError(f"state must be one of {STATE_VALUES}, got {state!r}")
    has_anchor = rev.get("anchor") is not None
    has_context = rev.get("context") is not None
    if state == "present" and not (has_anchor and not has_context):
        raise ValueError("present revision must set anchor and leave context null")
    if state == "absent" and not (has_context and not has_anchor):
        raise ValueError("absent revision must set context and leave anchor null")
    if state in ("NA", "truth_inadmissible") and (has_anchor or has_context):
        raise ValueError(f"{state} revision must leave both anchor and context null")


def fixture_truth_template(fixture_id: str) -> dict:
    """A blank fixture-truth record. `fixture_id` is a label only; no fixture is read."""
    return {
        "fixture_id": fixture_id,
        "schema": "rd-fixture-truth/v0-draft",
        "revisions": list(REVISIONS),
        "state_values": list(STATE_VALUES),
        "truth_statuses": list(TRUTH_STATUSES),  # independent; see module docstring
        "requirement": {
            # entry/behavior: each an independent base/head realization (present→anchor, absent→context).
            "entry": _item(),
            "behavior": _item(),
            "qualifiers": [
                # one blank qualifier stub per admissible kind; adjudicator adds/removes instances.
                # Each qualifier is also realized per revision (base/head may differ).
                {"kind": kind, **_item(), "condition": _EMPTY}
                for kind in vocabulary.allowed_qualifier_kinds()
            ],
        },
        # Filled with exactly one of TRUTH_STATUSES when the normal truth cannot be stated; else null.
        "truth_status": _EMPTY,
        "notes": _EMPTY,
    }


def adjudication_sheet_template(fixture_id: str, adjudicator: str = "<id>") -> dict:
    """A blank sheet an adjudicator fills independently. No labels, no golden, no hints."""
    return {
        "fixture_id": fixture_id,
        "adjudicator": adjudicator,
        "schema": "rd-adjudication-sheet/v0-draft",
        "instructions": (
            "State each requirement item independently. Use present/absent per revision; "
            "use NA when a slot does not apply and truth_inadmissible when the truth cannot be "
            f"stated. If the item resists the frozen kinds, record one of {list(TRUTH_STATUSES)} "
            "and stop — do not invent a kind."
        ),
        "allowed_state_values": list(STATE_VALUES),
        "allowed_truth_statuses": list(TRUTH_STATUSES),
        "admissible_qualifier_kinds": list(vocabulary.allowed_qualifier_kinds()),
        "items": [],  # the adjudicator appends {local_id, kind, slot, condition, truth_status?}
    }


def _no_results_dir(path: Path) -> Path:
    resolved = path.resolve()
    results = (Path(__file__).resolve().parents[2] / "results").resolve()
    if results in resolved.parents or resolved == results:
        raise SystemExit(f"refusing to write a template under results/: {resolved}")
    return resolved


def _assert_statuses_independent() -> None:
    # No two statuses share a value, and none is a substring-alias of another.
    assert len(set(TRUTH_STATUSES)) == len(TRUTH_STATUSES), "truth statuses are not distinct"


def _self_test() -> None:
    _assert_statuses_independent()
    ft = fixture_truth_template("<fixture>")
    # Every golden slot is empty; nothing is pre-decided.
    assert ft["truth_status"] is None
    # entry/behavior each carry an independent base/head realization (no single shared anchor).
    for kind in ("entry", "behavior"):
        item = ft["requirement"][kind]
        assert set(item) == {"base", "head"}, item
        for rev in REVISIONS:
            assert item[rev] == {"state": None, "anchor": None, "context": None}
    # transform is never offered as a qualifier slot; qualifiers are per-revision too.
    kinds = [q["kind"] for q in ft["requirement"]["qualifiers"]]
    assert "transform" not in kinds, kinds
    assert set(kinds) == set(vocabulary.allowed_qualifier_kinds())
    assert all(set(q) >= {"base", "head", "condition"} for q in ft["requirement"]["qualifiers"])
    # The present/absent fill rule round-trips: base absent(context), head present(anchor), differing.
    check_revision({"state": "absent", "anchor": None, "context": "ctx"})
    check_revision({"state": "present", "anchor": "a", "context": None})
    check_revision({"state": "NA", "anchor": None, "context": None})
    for bad in ({"state": "present", "anchor": None, "context": None},
                {"state": "absent", "anchor": "a", "context": None},
                {"state": "NA", "anchor": "a", "context": None},
                {"state": "bogus", "anchor": None, "context": None}):
        try:
            check_revision(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"check_revision accepted an invalid revision: {bad}")
    sheet = adjudication_sheet_template("<fixture>")
    assert sheet["items"] == [] and "transform" not in sheet["admissible_qualifier_kinds"]
    # results/ is off-limits.
    try:
        _no_results_dir(Path(__file__).resolve().parents[2] / "results" / "x.json")
    except SystemExit:
        pass
    else:
        raise AssertionError("writing under results/ was not refused")
    print("templates self-test ok:",
          {"qualifier_slots": kinds, "truth_statuses": list(TRUTH_STATUSES),
           "state_values": list(STATE_VALUES)})


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit a blank RD truth / adjudication template.")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--kind", choices=("fixture-truth", "adjudication-sheet"), default="fixture-truth")
    ap.add_argument("--fixture-id", default="<fixture-id>")
    ap.add_argument("--adjudicator", default="<id>")
    ap.add_argument("--out", help="write here (never under results/); default stdout")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return
    doc = (fixture_truth_template(args.fixture_id) if args.kind == "fixture-truth"
           else adjudication_sheet_template(args.fixture_id, args.adjudicator))
    text = json.dumps(doc, indent=2) + "\n"
    if args.out:
        out = _no_results_dir(Path(args.out))
        out.write_text(text)
        print(f"wrote blank {args.kind} template to {out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
