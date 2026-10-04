import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd"))

import conformance as K


def _m(**kw):
    base = {"true_verified": 0, "true_unverified": 0, "true_contradicted": 0, "false_verified": 0,
            "false_unverified": 0, "false_contradicted": 0, "caught_by_anchor": 0, "tool_failures": 0,
            "hops": {}}
    return {**base, **kw}


def test_provider_statuses_follow_the_charter():
    v = {
        "codeql/go/a": _m(true_verified=2, false_unverified=1, class_="x"),
        "codeql/go/b": _m(true_verified=1, true_unverified=1, false_unverified=1),
        "codeql/go/c": _m(true_unverified=2, false_unverified=1),
        "codeql/go/d": _m(true_verified=2, false_verified=1),
        "codeql/go/e": _m(tool_failures=3),
    }
    classes = {"codeql/go/a": "SUPPORTED", "codeql/go/b": "PARTIAL", "codeql/go/c": "BLIND",
               "codeql/go/d": "UNSAFE", "codeql/go/e": "INCONCLUSIVE_TOOL_FAILURE"}
    for k, c in classes.items():
        v[k]["class"] = c
    t = K.provider_table(v)
    assert {k: t[k]["status"] for k in t} == {
        "codeql/go/a": "SUPPORTED", "codeql/go/b": "PARTIAL", "codeql/go/c": "UNSUPPORTED",
        "codeql/go/d": "NON_CONFORMANT", "codeql/go/e": "TOOL_FAILURE"}


def test_blind_spots_and_disagreements_are_listed_by_name():
    hops = {"r01": {"label": True, "state": "VERIFIED", "name": "hit"},
            "r02": {"label": True, "state": "UNVERIFIED", "name": "blind"},
            "r03": {"label": False, "state": "VERIFIED", "name": "false-verified"},
            "r04": {"label": True, "state": "CONTRADICTED", "name": "true-contradicted"},
            "r05": {"label": False, "state": "UNVERIFIED", "name": "correct-negative"}}
    t = K.provider_table({"codeql/go/x": {**_m(), "hops": hops, "class": "UNSAFE"}})["codeql/go/x"]
    assert t["blind_spots"] == ["blind"]  # a blind spot is not a disagreement
    assert t["disagreements"] == ["false-verified", "true-contradicted"]


def test_truth_vocabulary_takes_each_groups_last_round():
    tv = K.truth_vocabulary()
    assert tv["transform"]["outcome"] == "EXIT_VOCABULARY" and tv["transform"]["round"] == 2
    assert tv["guard"] == {"round": 2, "outcome": "ADMISSIBLE", "indeterminate_rules": []}
    assert tv["entry"]["round"] == 1 and tv["entry"]["outcome"] == "ADMISSIBLE"
    relations = [g for g in tv if "/" in g]
    assert len(relations) == 9 and all(tv[g]["outcome"] == "ADMISSIBLE" for g in relations)


# ---- attempts: one infrastructure retry, only after a tool failure ---------------------------


def _attempt(n, fixtures_run, statuses, states):
    return {"attempt": n, "provenance": {"fixtures_run": fixtures_run, "analysis_status": statuses},
            "states": states}


OK_STATES = {"r01": {"fixture": "go", "state": "VERIFIED"}, "r02": {"fixture": "py", "state": "UNVERIFIED"}}


def test_first_run_runs_everything():
    assert K.plan([]) == (1, None, "")


def test_a_clean_result_is_never_rerun():
    a1 = _attempt(1, ["go", "py"], {"go": "ok", "py": "ok"}, OK_STATES)
    n, _, refusal = K.plan([a1])
    assert n == 0 and "never rerun" in refusal


def test_a_tool_failure_allows_one_retry_of_the_failed_fixtures_only():
    states = {"r01": {"fixture": "go", "state": "VERIFIED"}, "r02": {"fixture": "py", "state": "TOOL_FAILURE"}}
    a1 = _attempt(1, ["go", "py"], {"go": "ok", "py": "tool_failure"}, states)
    assert K.plan([a1]) == (2, ["py"], "")
    a2 = _attempt(2, ["py"], {"py": "tool_failure"}, {"r02": {"fixture": "py", "state": "TOOL_FAILURE"}})
    n, _, refusal = K.plan([a1, a2])
    assert n == 0 and "no attempt 3" in refusal  # a second failure leaves the gate inconclusive


def test_the_retry_replaces_only_the_rerun_fixtures_verdicts():
    a1 = _attempt(1, ["go", "py"], {"go": "ok", "py": "tool_failure"},
                  {"r01": {"fixture": "go", "state": "VERIFIED"}, "r02": {"fixture": "py", "state": "TOOL_FAILURE"}})
    a2 = _attempt(2, ["py"], {"py": "ok"}, {"r02": {"fixture": "py", "state": "UNVERIFIED"}})
    assert K.merged([a1, a2]) == {"r01": {"fixture": "go", "state": "VERIFIED"},
                                   "r02": {"fixture": "py", "state": "UNVERIFIED"}}


# ---- integrity: the expected set drives the gate ---------------------------------------------


CASES = {"fixtures": {"g": {"language": "go"}, "p": {"language": "python"}},
         "hops": [{"id": "r01", "fixture": "g", "relation": "def_use"},
                  {"id": "r02", "fixture": "g", "relation": "def_use"},
                  {"id": "r03", "fixture": "p", "relation": "def_use"},
                  {"id": "r04", "fixture": "p", "relation": "def_use"}]}
LABELS = {"r01": {"label": True}, "r02": {"label": False}, "r03": {"label": True}, "r04": {"label": False}}
REQUIRED = ["codeql/go/def_use", "codeql/python/def_use"]
STATES = {k: {} for k in LABELS}


def test_integrity_holds_for_a_complete_table():
    assert K.integrity_problems(REQUIRED, CASES, LABELS, REQUIRED, STATES) == []


def test_a_missing_or_extra_verifier_is_protocol_invalid():
    p = K.integrity_problems(REQUIRED, CASES, LABELS, ["codeql/go/def_use"], STATES)
    assert p and K.gate(p, {}) == "PROTOCOL_INVALID"
    p = K.integrity_problems(REQUIRED, CASES, LABELS, [*REQUIRED, "codeql/go/extra"], STATES)
    assert p


def test_a_verifier_without_a_true_or_false_case_is_protocol_invalid():
    labels = {**LABELS, "r04": {"label": True}}
    assert any("no admissible FALSE" in x for x in K.integrity_problems(REQUIRED, CASES, labels, REQUIRED, STATES))
    cases = {**CASES, "hops": [*CASES["hops"], {"id": "r05", "fixture": "g", "relation": "range_element"}]}
    labels = {**LABELS, "r05": {"label": True}}
    states = {**STATES, "r05": {}}
    assert any("no required verifier" in x for x in K.integrity_problems(REQUIRED, cases, labels, REQUIRED, states))


def test_gate_status():
    assert K.gate([], {"x": {"status": "SUPPORTED"}, "y": {"status": "UNSUPPORTED"}}) == "READY"
    assert K.gate([], {"x": {"status": "NON_CONFORMANT"}}) == "READY"  # a result, not a failure
    assert K.gate([], {"x": {"status": "TOOL_FAILURE"}}) == "INCONCLUSIVE_TOOL_FAILURE"
    assert K.gate(["missing"], {}) == "PROTOCOL_INVALID"


def test_required_verifiers_come_from_the_frozen_truth_vocabulary():
    assert K.required_verifiers(K.truth_vocabulary()) == sorted(
        f"codeql/{lang}/{rel}" for lang, rels in (("go", ["argument_binding", "def_use", "field_flow",
                                                          "guard_property", "object_composition", "range_element"]),
                                                  ("python", ["call_typed_attribute", "def_use", "registry_dispatch"]))
        for rel in rels)


# ---- attempt 2 runs on attempt 1's instrument -------------------------------------------------


FIRST = {"harness": {"commit": "a" * 40, "dirty": False}, "codeql": "codeql-bundle-v2.27.1",
         "files": {"experiments/hop_bridge/queries/go/DefUse.ql": "1" * 64, "experiments/rd/conformance.py": "2" * 64}}


def _now(**kw):
    return {"commit": FIRST["harness"]["commit"], "codeql": FIRST["codeql"], "files": dict(FIRST["files"]), **kw}


def test_same_instrument_allows_the_retry():
    assert K.retry_problems(FIRST, _now()) == []


def test_a_changed_commit_refuses_the_retry():
    assert any("harness commit" in p for p in K.retry_problems(FIRST, _now(commit="b" * 40)))


def test_a_changed_query_refuses_the_retry_even_with_the_same_commit_field():
    files = {**FIRST["files"], "experiments/hop_bridge/queries/go/DefUse.ql": "9" * 64}
    problems = K.retry_problems(FIRST, _now(files=files))
    assert problems and "DefUse.ql" in problems[0]
    assert any("instrument files" in p for p in K.retry_problems(FIRST, _now(files={**files, "new.ql": "0" * 64})))


def test_a_changed_codeql_refuses_the_retry():
    assert any("CodeQL" in p for p in K.retry_problems(FIRST, _now(codeql="codeql-bundle-v2.28.0")))
