"""RD fixture selection (experiments/rd/selection.py), on synthetic advisories only: these tests never
open the OSV snapshot."""

import argparse
import ast
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd"))

import selection as S

SHA = "a" * 40
SHA2 = "b" * 40


def rec(**kw):
    base = {"_ecosystem_file": "Go", "id": "GO-2026-0001", "published": "2026-03-01T00:00:00Z",
            "references": [{"type": "FIX", "url": f"https://github.com/acme/widget/commit/{SHA}"}],
            "database_specific": {"cwe_ids": ["CWE-22"]}}
    return {**base, **kw}


# ---- the gated snapshot ---------------------------------------------------------------------------


def test_only_open_snapshot_reads_the_zips_and_it_checks_the_gate_first():
    tree = ast.parse((ROOT / "experiments" / "rd" / "selection.py").read_text())
    readers = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "ZipFile"]
    assert len(readers) == 1
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "open_snapshot")
    first = fn.body[1]  # after the docstring
    assert "gate_ready" in ast.unparse(first)


def test_a_closed_gate_keeps_the_snapshot_closed(monkeypatch):
    monkeypatch.setattr(S.conformance, "gate_ready", lambda: False)
    with pytest.raises(SystemExit, match="not READY"):
        S.open_snapshot()


# ---- advisory-level filters -----------------------------------------------------------------------


def test_fix_commit_extraction():
    assert S.fix_commits(rec()) == {("https://github.com/acme/widget", SHA)}
    pr = rec(references=[{"url": "https://github.com/acme/widget/pull/12"}])
    assert S.fix_commits(pr) == set()  # a pull request is not a commit
    git = rec(references=[], affected=[{"ranges": [{"type": "GIT", "repo": "https://github.com/Acme/Widget.git",
                                                    "events": [{"introduced": "0"}, {"fixed": SHA}]}]}])
    assert S.fix_commits(git) == {("https://github.com/acme/widget", SHA)}
    sub = rec(references=[{"url": f"https://gitlab.com/group/sub/project/-/commit/{SHA}"}])
    assert S.fix_commits(sub) == {("https://gitlab.com/group/sub/project", SHA)}  # GitLab subgroups
    deep = rec(references=[{"url": f"https://github.com/acme/widget/extra/commit/{SHA}"}])
    assert S.fix_commits(deep) == set()


def test_advisory_filters():
    assert S.advisory_filter(rec())[0] == "PASS"
    assert S.advisory_filter(rec(_ecosystem_file="npm"))[0] == "WRONG_ECOSYSTEM"
    assert S.advisory_filter(rec(withdrawn="2026-04-01T00:00:00Z"))[0] == "WITHDRAWN"
    assert S.advisory_filter(rec(published="2025-12-31T23:59:59Z"))[0] == "OUT_OF_WINDOW"
    assert S.advisory_filter(rec(published="2026-09-30T00:00:00Z"))[0] == "OUT_OF_WINDOW"  # end excluded
    assert S.advisory_filter(rec(references=[]))[0] == "NO_FIX_COMMIT"
    two = rec(references=[{"url": f"https://github.com/acme/widget/commit/{SHA}"},
                          {"url": f"https://github.com/acme/widget/commit/{SHA2}"}])
    assert S.advisory_filter(two)[0] == "MULTIPLE_FIX_COMMITS"
    retired = rec(references=[{"url": f"https://github.com/caddyserver/caddy/commit/{SHA}"}])
    assert S.advisory_filter(retired)[0] == "RETIRED_REPOSITORY"


def test_cwe_classes():
    assert S.cwe_classes([22, 36]) == ["path-traversal"]
    assert S.cwe_classes([22, 79]) == ["path-traversal", "xss"]  # a candidate counts in every class
    assert S.cwe_classes([1234]) == ["CWE-1234"] and S.cwe_classes([]) == ["none"]


def test_pool_dedupes_aliases_and_orders_by_seed():
    recs = [rec(id="GO-2026-0001"), rec(_ecosystem_file="PyPI", id="GHSA-x", published="2026-02-01T00:00:00Z")]
    recs += [rec(id=f"GO-2026-{i:04d}", references=[{"url": f"https://github.com/o{i}/r{i}/commit/{SHA}"}])
             for i in range(2, 12)]
    a, b = S.build_pool(recs), S.build_pool(list(reversed(recs)))
    assert a["queues"] == b["queues"]  # the order depends only on the seed, not on input order
    assert a["filter_counts"]["DUPLICATE_FIX_COMMIT"] == 1  # one fix commit is one candidate, whatever ecosystem lists it
    assert [c["position"] for c in a["queues"]["go"]] == list(range(1, len(a["queues"]["go"]) + 1))


def test_aliases_merge_their_cwe_metadata():
    go = rec(id="GO-2026-0001", database_specific={"cwe_ids": ["CWE-22"]})
    ghsa = rec(id="GHSA-y", published="2026-04-01T00:00:00Z", database_specific={"cwe_ids": ["CWE-79"]})
    pool = S.build_pool([go, ghsa])
    assert pool["filter_counts"]["DUPLICATE_FIX_COMMIT"] == 1
    (cand,) = pool["queues"]["go"]
    assert cand["id"] == "GO-2026-0001" and cand["cwe_classes"] == ["path-traversal", "xss"]
    assert "GHSA-y" in cand["aliases"]
    assert cand["listed_in"] == {"GO-2026-0001": "go", "GHSA-y": "go"}


def test_a_fix_listed_by_both_ecosystems_records_where_it_came_from():
    go = rec(id="GO-2026-0001")
    py = rec(_ecosystem_file="PyPI", id="GHSA-x", published="2026-02-01T00:00:00Z")
    pool = S.build_pool([go, py])
    (cand,) = pool["queues"]["python"]  # the earliest published listing decides the queue
    assert pool["queues"]["go"] == [] and cand["listed_in"] == {"GHSA-x": "python", "GO-2026-0001": "go"}


# ---- diff-level filters and fetching ---------------------------------------------------------------


def test_diff_level_filters():
    assert S.diff_outcome([(3, 1, "pkg/a.go"), (40, 0, "pkg/a_test.go")], "go")[0] == "PASS"
    assert S.diff_outcome([(40, 0, "pkg/a_test.go")], "go")[0] == "NO_LANGUAGE_SOURCE_CHANGE"
    assert S.diff_outcome([(1, 1, "go.mod"), (5, 5, "go.sum")], "go")[0] == "NO_LANGUAGE_SOURCE_CHANGE"
    assert S.diff_outcome([(150, 60, "pkg/a.go"), (900, 0, "tests/test_a.py")], "go")[0] == "DIFF_TOO_LARGE"
    out, facts = S.diff_outcome([(2, 2, "vendor/x/y.go")], "go")
    assert out == "PASS" and facts["vendored_only"]  # vendored code is a manual check (VENDORED_CODE)
    assert S.diff_outcome([(3, 0, "src/pkg/core.py"), (9, 0, "tests/test_core.py")], "python")[0] == "PASS"


def test_fetch_errors_split_into_candidate_property_and_infrastructure():
    assert S.classify_fetch_error("fatal: remote error: upload-pack: not our ref " + SHA) == "COMMIT_UNAVAILABLE"
    assert S.classify_fetch_error("remote: Repository not found.") == "COMMIT_UNAVAILABLE"
    assert S.classify_fetch_error("fatal: unable to access: Could not resolve host: github.com") == "FETCH_FAILED"
    assert S.classify_fetch_error("timeout") == "FETCH_FAILED"
    # ambiguous (permissions, configuration, transport): infrastructure, not a rejection
    assert S.classify_fetch_error("fatal: '...' does not appear to be a git repository") == "FETCH_FAILED"
    assert "FETCH_FAILED" not in S.MECHANICAL  # never an outcome that finishes a candidate
    assert "NOT_SINGLE_PARENT" in S.MECHANICAL  # a merge or root fix commit is excluded, not guessed


# ---- the log, the protocol provenance ---------------------------------------------------------------


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "LOG", tmp_path / "log.jsonl")
    return tmp_path


def test_the_log_is_hash_chained(tmp_log):
    S.append_log({"step": "pool"})
    S.append_log({"step": "screen", "id": "x", "outcome": "PASS"})
    assert S.chain_problems(S.log_entries()) == []
    lines = S.LOG.read_text().splitlines()
    S.LOG.write_text(lines[0].replace("pool", "poo1") + "\n" + lines[1] + "\n")
    assert S.chain_problems(S.log_entries())


def test_after_pool_the_script_and_the_pool_cannot_change(tmp_log):
    pool_bytes = b'{"script_sha256": "x"}'
    S.append_log({"step": "pool", "pool_sha256": hashlib.sha256(pool_bytes).hexdigest()})
    problems = S.protocol_problems({"script_sha256": "x"}, pool_bytes, S.log_entries())
    assert problems == ["selection.py differs from the script that wrote the pool"]
    good = {"script_sha256": S.script_sha256()}
    assert S.protocol_problems(good, pool_bytes, S.log_entries()) == []
    assert S.protocol_problems(good, pool_bytes + b" ", S.log_entries()) == [
        "the candidate pool differs from the one logged by `pool`"]


# ---- screening order, fetch failures --------------------------------------------------------------


def _pool(go_ids, py_ids=()):
    def c(i, lang, pos):
        return {"id": i, "language": lang, "position": pos, "repo": f"https://github.com/o/{i}",
                "fix_commit": SHA, "cwe_classes": ["path-traversal"]}
    return {"queues": {"go": [c(i, "go", n) for n, i in enumerate(go_ids, 1)],
                       "python": [c(i, "python", n) for n, i in enumerate(py_ids, 1)]}}


def _accept(*ids):
    out = []
    for i in ids:
        out += [{"step": "screen", "id": i, "outcome": "PASS"}, {"step": "decide", "id": i, "verdict": "ACCEPTED"}]
    return out


def test_screening_goes_strictly_in_pool_order():
    pool = _pool(["g1", "g2", "g3"])
    assert S.next_candidate(pool, "go", [])["id"] == "g1"
    entries = [{"step": "screen", "id": "g1", "outcome": "DIFF_TOO_LARGE"}]
    assert S.next_candidate(pool, "go", entries)["id"] == "g2"
    entries += [{"step": "screen", "id": "g2", "outcome": "PASS"}]
    assert S.next_candidate(pool, "go", entries)["id"] == "g2"  # awaiting its manual verdict


def test_a_failed_fetch_keeps_the_candidate_pending_and_halts_after_the_last_attempt():
    pool = _pool(["g1", "g2"])
    entries = [{"step": "fetch_failed", "id": "g1"}]
    assert S.next_candidate(pool, "go", entries)["id"] == "g1" and S.halted(entries) == []
    entries = entries * S.FETCH_ATTEMPTS
    assert S.halted(entries) == ["g1"]  # INCONCLUSIVE_INFRA: no moving on to g2


# ---- the queue -----------------------------------------------------------------------------------


def test_queue_quotas_and_roles():
    pool = _pool([f"g{i}" for i in range(1, 9)])
    pool["queues"]["go"][1]["repo"] = pool["queues"]["go"][0]["repo"]  # g2: same repository as g1
    for i, c in enumerate(pool["queues"]["go"]):
        c["cwe_classes"] = ["path-traversal"] if i < 3 else [f"class-{i}"]
    queues, skipped = S.build_queue(pool, _accept(*[f"g{i}" for i in range(1, 9)]))
    ids = [c["id"] for c in queues["go"]]
    assert ids == ["g1", "g3", "g4", "g5", "g6", "g7"]  # g2 duplicate repository; quota allows g1, g3
    assert {x["id"]: x["reason"] for x in skipped} == {"g2": "DUPLICATE_REPOSITORY"}
    assert [c["role"] for c in queues["go"]] == ["primary"] * 4 + ["reserve"] * 2


def test_cwe_quota_counts_across_languages_and_turns_alternate():
    pool = _pool(["g1", "g2"], ["p1", "p2"])
    queues, skipped = S.build_queue(pool, _accept("g1", "g2", "p1", "p2"))
    first, second = S.turn_order(["go", "python"], 1)
    # position 1: both languages queue their first candidate, filling the shared class
    assert [c["id"] for c in queues[first]] == [f"{first[0]}1"]
    assert [c["id"] for c in queues[second]] == [f"{second[0]}1"]
    assert [x["reason"] for x in skipped] == ["CWE_CLASS_QUOTA"] * 2
    assert S.turn_order(["go", "python"], 2) == [second, first]  # the turns really alternate
    assert S.turn_order(["python", "go"], 1) == S.turn_order(["go", "python"], 1)  # seeded, not by input


def test_the_last_place_in_a_class_goes_to_whoever_picks_first_at_that_position():
    pool = _pool(["g1", "g2"], ["p1", "p2"])
    first, second = S.turn_order(["go", "python"], 1)
    q = {"go": pool["queues"]["go"], "python": pool["queues"]["python"]}
    q[first][0]["cwe_classes"] = ["shared"]   # position 1: one place of "shared" taken
    q[second][0]["cwe_classes"] = ["own"]
    q[first][1]["cwe_classes"] = ["shared"]   # position 2: both want the last place
    q[second][1]["cwe_classes"] = ["shared"]
    queues, skipped = S.build_queue(pool, _accept("g1", "g2", "p1", "p2"))
    # position 2 reverses the order: `second` picks first there and gets the last place
    assert [c["id"] for c in queues[second]] == [q[second][0]["id"], q[second][1]["id"]]
    assert [c["id"] for c in queues[first]] == [q[first][0]["id"]]
    assert skipped == [{"id": q[first][1]["id"], "reason": "CWE_CLASS_QUOTA", "classes": ["shared"]}]


def test_a_multi_cwe_candidate_takes_a_place_in_every_class():
    pool = _pool(["g1", "g2", "g3"])
    pool["queues"]["go"][0]["cwe_classes"] = ["path-traversal", "xss"]
    pool["queues"]["go"][1]["cwe_classes"] = ["xss"]
    pool["queues"]["go"][2]["cwe_classes"] = ["xss"]
    queues, skipped = S.build_queue(pool, _accept("g1", "g2", "g3"))
    assert [c["id"] for c in queues["go"]] == ["g1", "g2"]  # g1 and g2 fill xss
    assert skipped == [{"id": "g3", "reason": "CWE_CLASS_QUOTA", "classes": ["xss"]}]


def test_manual_verdicts_are_a_frozen_enumeration(tmp_log):
    args = argparse.Namespace(id="g1", verdict="TOO_HARD", route=None, evidence="x")
    with pytest.raises(SystemExit, match="frozen"):
        S.decide(args)
    assert "REVIEW_BOUNDARY_REACHED" in S.MANUAL and set(S.ROUTES) == {"TEST", "POC", "PROBE"}
