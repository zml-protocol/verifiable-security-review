"""Invariants for the RD agent scaffold (experiments/rd/agent) and truth templates.

These lock the freeze guarantees Codex asked for: phase A immutable after lock and its seal covering
the full structured requirement payload (anchors, qualifier fields, per-revision state, rationale,
and the unsupported-type proposal), phase B sealed over its full content with phase C catching live
mutation, caller payload isolated, and the present/absent per-revision template schema. The suite is
0-xfail — the phase-A-payload gap is closed.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "agent"))
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))

import phases  # noqa: E402
import templates  # noqa: E402
import verifiability  # noqa: E402

GATE = verifiability.verifiable_pair


def _locked_a():
    a = phases.PhaseA()
    a.add("r1", "entry")
    a.add("r2", "behavior")
    a.add("r3", "guard")
    a.add("r4", "transform")  # blind spot
    a.lock()
    return a


def test_phase_a_locks_and_classifies():
    a = _locked_a()
    with pytest.raises(phases.PhaseError):
        a.add("r5", "entry")
    blind = [i for i in a.items() if i.is_blind_spot]
    assert [i.local_id for i in blind] == ["r4"]
    assert blind[0].slot == phases.UNSUPPORTED_REQUIREMENT_TYPE
    assert a.report()["phrase"] == phases.REPORT_PHRASE


def test_verifiability_is_boolean_only():
    # SUPPORTED/PARTIAL pairs verifiable; unknown pair and empty are not.
    assert GATE("go", "def_use") is True
    assert GATE("go", "argument_binding") is True  # PARTIAL
    assert GATE("go", "no_such_relation") is False
    assert GATE(None, None) is False


def test_phase_b_cannot_realize_blind_spot():
    a = _locked_a()
    b = phases.PhaseB(a, GATE)
    with pytest.raises(phases.PhaseError):
        b.realize(phases.Realization("r4"))


def test_phase_b_seal_covers_payload_and_c_catches_mutation():
    a = _locked_a()
    b = phases.PhaseB(a, GATE)
    b.realize(phases.Realization("r1", payload={"anchor": "x"}))
    b.realize(phases.Realization("r2", relation="def_use", language="go"))
    b.lock()
    c = phases.PhaseC(a, b)
    assert c.inputs_frozen()

    # mutate payload of a locked realization -> C fails loud
    b.realizations()[0].payload["anchor"] = "y"
    with pytest.raises(phases.PhaseError):
        c.inputs_frozen()
    b.realizations()[0].payload["anchor"] = "x"
    assert c.inputs_frozen()

    # mutate verifiable of a locked realization -> C fails loud
    saved = b.realizations()[1].verifiable
    b.realizations()[1].verifiable = not saved
    with pytest.raises(phases.PhaseError):
        c.inputs_frozen()
    b.realizations()[1].verifiable = saved
    assert c.inputs_frozen()


def test_caller_payload_mutation_is_isolated():
    a = _locked_a()
    b = phases.PhaseB(a, GATE)
    caller = {"anchor": "orig"}
    stored = b.realize(phases.Realization("r1", payload=caller))
    caller["anchor"] = "tampered"
    assert stored.payload["anchor"] == "orig"


def test_phase_c_catches_phase_a_mutation():
    a = _locked_a()
    b = phases.PhaseB(a, GATE)
    b.realize(phases.Realization("r1"))
    b.lock()
    c = phases.PhaseC(a, b)
    a._items.append(phases.RequirementItem("sneak", "entry"))
    with pytest.raises(phases.PhaseError):
        c.inputs_frozen()


def test_template_present_absent_schema():
    ft = templates.fixture_truth_template("<f>")
    for kind in ("entry", "behavior"):
        item = ft["requirement"][kind]
        assert set(item) == {"base", "head"}
        for rev in templates.REVISIONS:
            assert item[rev] == {"state": None, "anchor": None, "context": None}
    kinds = [q["kind"] for q in ft["requirement"]["qualifiers"]]
    assert "transform" not in kinds


def test_check_revision_enforces_fill_rule():
    templates.check_revision({"state": "present", "anchor": "a", "context": None})
    templates.check_revision({"state": "absent", "anchor": None, "context": "c"})
    templates.check_revision({"state": "NA", "anchor": None, "context": None})
    for bad in ({"state": "present", "anchor": None, "context": None},
                {"state": "absent", "anchor": "a", "context": None},
                {"state": "NA", "anchor": "a", "context": None},
                {"state": "bogus", "anchor": None, "context": None}):
        with pytest.raises(ValueError):
            templates.check_revision(bad)


def test_truth_statuses_stay_independent():
    assert len(set(templates.TRUTH_STATUSES)) == 4
    # UNSUPPORTED_REQUIREMENT_TYPE is shared by name with phases but is its own distinct status here.
    assert phases.UNSUPPORTED_REQUIREMENT_TYPE in templates.TRUTH_STATUSES


# ---- C.2: phase-A full structured-payload sealing (no xfail: 0 xfail before the real RD agent) ----

def _a_with_payloads():
    a = phases.PhaseA()
    a.add("r1", "entry", {"anchor": {"span": [1, 2]}, "rationale": "entry point"})
    a.add("r2", "behavior", {"anchor": {"span": [5, 6]}})
    a.add("r3", "guard", {"subject_anchor": {"span": [3, 3]}, "expected_semantic_field": "must_hold",
                          "state": {"base": {"state": "absent", "context": {"span": [3, 3]}},
                                    "head": {"state": "present", "anchor": {"span": [3, 3]}}},
                          "rationale": "guards the path"})
    a.add("r4", "transform", {"proposed_kind": "transform", "rationale": "changed transform"})
    a.lock()
    return a


def test_phase_a_seal_covers_full_payload():
    a = _a_with_payloads()
    pub = {i.local_id: i.public() for i in a.items()}
    assert "payload" in pub["r3"] and pub["r3"]["payload"]["expected_semantic_field"] == "must_hold"
    # the unsupported-type proposal is sealed as part of the artifact, not dropped
    assert pub["r4"]["slot"] == phases.UNSUPPORTED_REQUIREMENT_TYPE
    assert pub["r4"]["payload"]["proposed_kind"] == "transform"


@pytest.mark.parametrize("mutate", [
    lambda a: a.items()[0].payload.__setitem__("anchor", {"span": [9, 9]}),          # entry anchor
    lambda a: a.items()[2].payload["state"]["base"].__setitem__("context", {"span": [9, 9]}),  # absent context
    lambda a: a.items()[2].payload.__setitem__("expected_semantic_field", "must_not_hold"),    # qualifier field
    lambda a: a.items()[3].payload.__setitem__("proposed_kind", "something_else"),   # unsupported proposal
    lambda a: a.items()[2].payload.__setitem__("rationale", "rewritten reasoning"),  # rationale is sealed
    lambda a: a._items.append(phases.RequirementItem("r9", "entry")),               # add a qualifier/item
    lambda a: a._items.pop(),                                                        # remove an item
])
def test_phase_a_post_lock_mutation_is_caught(mutate):
    a = _a_with_payloads()
    b = phases.PhaseB(a, GATE)
    b.realize(phases.Realization("r1"))
    b.lock()
    c = phases.PhaseC(a, b)
    assert c.inputs_frozen()
    mutate(a)
    with pytest.raises(phases.PhaseError):
        c.inputs_frozen()


def test_phase_a_external_dict_is_isolated():
    a = phases.PhaseA()
    external = {"anchor": {"span": [1, 2]}, "rationale": "r"}
    a.add("r1", "entry", external)
    a.lock()
    seal = a.seal
    external["anchor"]["span"] = [9, 9]          # caller mutates the dict they passed
    external["rationale"] = "tampered"
    assert phases._require_frozen(a) == seal       # sealed artifact is unaffected
