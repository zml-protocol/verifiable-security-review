import copy
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "provider_reach"))

import reach

from spike.gitrepo import GitRepo

SPEC = ROOT / "experiments/provider_reach/endpoints.yaml"


def _spec():
    return yaml.safe_load(SPEC.read_text())


def test_spec_locations_match_goldens_and_hide_intermediates():
    spec = _spec()
    for fid, fixture in spec["fixtures"].items():
        for side in reach.SIDES:
            locs = reach._locations(fixture, side)
            ends = fixture["endpoints"][side]
            for end in (ends["source"], ends["sink"]):  # no endpoint on a golden intermediate
                for loc in locs:
                    lo, hi = reach._span(loc["lines"])
                    assert not (end["file"] == loc["file"] and lo <= end["line"] <= hi), (fid, side, end)
            assert {loc["relation"] for loc in locs} <= set(spec["relations"])


def _item(file, line, granularity="dataflow"):
    return {"file": file, "start_line": line, "end_line": line, "granularity": granularity}


def _full_path(locs):
    items = []
    for x in locs:
        lines = x.get("anchors") or [reach._span(x["lines"])[0]]
        items += [_item(x["file"], ln) for ln in lines]
    return items


def _write(out, provider, fid, side, paths, status="ok"):
    d = out / provider / fid / side
    d.mkdir(parents=True, exist_ok=True)
    (d / "evidence.json").write_text(json.dumps({"status": status, "paths": paths}))


CALIBRATED = ("call_typed_attribute", "registry_dispatch", "object_composition", "field_flow")


def _score(tmp_path, spec=None, calibrated=None):
    spec_path = SPEC
    if spec is not None:
        spec_path = tmp_path / "spec.yaml"
        spec_path.write_text(yaml.safe_dump(spec))
    calibration = tmp_path / "calibration.json"
    verdicts = {r: True for r in CALIBRATED} | (calibrated or {})
    calibration.write_text(json.dumps({"provider": "codeql-2.27.1-taint-path",
                                       "relations": {r: {"expressible": v} for r, v in verdicts.items()}}))
    report = tmp_path / "report.json"
    reach.score(Namespace(spec=spec_path, out=tmp_path, report=report, calibration=calibration))
    return json.loads(report.read_text())


def _everything(tmp_path, codeql_paths, trailmark_status="ok"):
    for fid, fixture in _spec()["fixtures"].items():
        for side in reach.SIDES:
            locs = reach._locations(fixture, side)
            _write(tmp_path, "codeql", fid, side, codeql_paths(fid, side, locs))
            _write(tmp_path, "trailmark", fid, side,  # a function node spanning it all never counts
                   [[{"file": locs[0]["file"], "start_line": 1, "end_line": 10_000,
                      "granularity": "function"}]], status=trailmark_status)


def test_one_path_through_everything_gives_limited_scope(tmp_path):
    _everything(tmp_path, lambda f, s, locs: [_full_path(locs)])
    report = _score(tmp_path)
    cats = {(r["provider"].split("-")[0], r["relation"], r["category"]) for r in report["locations"]}
    assert ("trailmark", "field_flow", "NOT_EXPRESSIBLE") in cats
    assert ("codeql", "guard_property", "HIT_BUT_NOT_EXPRESSIBLE") in cats
    assert report["relation_viability"]["field_flow"]["state"] == "RECOVERED"
    assert report["relation_viability"]["guard_property"]["state"] == "NOT_EXPRESSIBLE_BY_ANY"
    assert report["decision"] == "B_LIMITED_SCOPE_TO_1A"


def test_relation_instance_cannot_be_stitched_from_two_paths(tmp_path):
    def split(fid, side, locs):  # each location on its own path
        return [[_item(x["file"], ln)] for x in locs for ln in (x.get("anchors") or [reach._span(x["lines"])[0]])]
    _everything(tmp_path, split)
    report = _score(tmp_path)
    assert report["relation_viability"]["object_composition"]["state"] == "EXPRESSIBLE_NOT_RECOVERED"
    assert report["relation_viability"]["field_flow"]["state"] == "EXPRESSIBLE_NOT_RECOVERED"
    assert report["decision"] == "B_GAPS_RECORDED"


def test_span_touch_without_anchors_does_not_recover_registry_dispatch(tmp_path):
    def only_verify_line(fid, side, locs):
        path = _full_path([x for x in locs if x["relation"] != "registry_dispatch"])
        return [path + [_item("authlib/jose/rfc7515/jws.py", 109)]]
    _everything(tmp_path, only_verify_line)
    report = _score(tmp_path)
    assert report["relation_viability"]["registry_dispatch"]["state"] == "EXPRESSIBLE_NOT_RECOVERED"


def test_tool_failure_is_inconclusive_not_a_capability_gap(tmp_path):
    spec = _spec()
    for fid in spec["fixtures"]:
        for side in reach.SIDES:
            _write(tmp_path, "codeql", fid, side, [], status="tool_failure")
            _write(tmp_path, "trailmark", fid, side, [])
    report = _score(tmp_path)
    assert report["relation_viability"]["field_flow"]["state"] == "INCONCLUSIVE_TOOL_FAILURE"
    assert report["decision"] == "INCONCLUSIVE_TOOL_FAILURE"


def test_another_provider_can_still_recover_despite_a_tool_failure(tmp_path):
    spec = copy.deepcopy(_spec())
    spec["expressible"]["trailmark-0.5.0"]["field_flow"] = True  # pretend, for this test only
    for fid, fixture in spec["fixtures"].items():
        for side in reach.SIDES:
            locs = reach._locations(fixture, side)
            _write(tmp_path, "codeql", fid, side, [], status="tool_failure")
            _write(tmp_path, "trailmark", fid, side, [_full_path(locs)])
    report = _score(tmp_path, spec)
    assert report["relation_viability"]["field_flow"]["state"] == "RECOVERED"


def test_calibration_decides_expressibility_and_is_required(tmp_path):
    _everything(tmp_path, lambda f, s, locs: [_full_path(locs)])
    report = _score(tmp_path, calibrated={"registry_dispatch": False})
    assert report["expressible"]["codeql-2.27.1-taint-path"]["registry_dispatch"] is False
    assert report["relation_viability"]["registry_dispatch"]["state"] == "NOT_EXPRESSIBLE_BY_ANY"
    try:
        reach.resolve_expressible(_spec(), tmp_path / "missing.json")
    except SystemExit as e:
        assert "calibrated" in str(e)
    else:
        raise AssertionError("scoring without a calibration must stop")


def test_codeql_workdir_is_rebuilt_on_every_attempt(tmp_path):
    ends = _spec()["fixtures"]["authlib-jws-none"]["endpoints"]["base"]
    first = reach.prepare_codeql_workdir(tmp_path, "python", ends)
    (first["pack"] / "stale.ql").write_text("stale")
    first["taint"].write_text("{}")
    (first["db"]).mkdir()
    second = reach.prepare_codeql_workdir(tmp_path, "python", ends)  # must not raise
    assert not (second["pack"] / "stale.ql").exists()
    assert not second["taint"].exists() and not second["db"].exists()
    assert 'line = 80 and name = "s"' in (second["pack"] / "Endpoints.qll").read_text()


def test_pilot_calibration_failure_is_not_a_plumbing_failure(tmp_path):
    spec = {"fixtures": {
        "plumb": {"expect_lines": [{"file": "a.py", "line": 5}], "codeql_role": "plumbing",
                  "trailmark_must_find_path": True},
        "calib": {"expect_lines": [{"file": "a.py", "line": 9}, {"file": "a.py", "line": 10}],
                  "codeql_role": "calibration", "calibrates": "registry_dispatch",
                  "trailmark_must_find_path": False},
    }}
    spec_path = tmp_path / "pilot.yaml"
    spec_path.write_text(yaml.safe_dump(spec))
    for fid, paths in (("plumb", [[_item("a.py", 5)]]), ("calib", [[_item("a.py", 10)]])):
        d = tmp_path / "codeql" / fid / "base"
        d.mkdir(parents=True)
        (d / "evidence.json").write_text(json.dumps(
            {"status": "ok", "source_nodes": 1, "sink_nodes": 1, "paths": paths}))
    calibration = tmp_path / "calibration.json"
    args = Namespace(spec=spec_path, out=tmp_path, provider="codeql", calibration=calibration)
    try:
        reach.pilot_check(args)
    except SystemExit as e:
        assert e.code == 0
    verdict = json.loads(calibration.read_text())["relations"]["registry_dispatch"]
    assert verdict == {"pilot": "calib", "expressible": False}  # 9 missing from the only path


def test_unresolved_endpoint_is_never_a_recovery_failure(tmp_path):
    for fid in _spec()["fixtures"]:
        for side in reach.SIDES:
            d = tmp_path / "codeql" / fid / side
            d.mkdir(parents=True)
            (d / "evidence.json").write_text(json.dumps(
                {"status": "ok", "source_nodes": 0, "sink_nodes": 3, "paths": []}))
            _write(tmp_path, "trailmark", fid, side, [])
    report = _score(tmp_path)
    cats = {r["category"] for r in report["locations"] if r["provider"].startswith("codeql")}
    assert "EXPRESSIBLE_NOT_RECOVERED" not in cats
    assert report["decision"] == "INCONCLUSIVE_TOOL_FAILURE"


def test_calibration_file_must_match_provider_and_cover_relations(tmp_path):
    bad = tmp_path / "old.json"
    bad.write_text(json.dumps({"provider": "codeql-2.20.0-taint-path", "relations": {}}))
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"provider": "codeql-2.27.1-taint-path",
                                   "relations": {"field_flow": {"expressible": True}}}))
    for path, message in ((bad, "calibration is for"), (partial, "lacks relations")):
        try:
            reach.resolve_expressible(_spec(), path)
        except SystemExit as e:
            assert message in str(e)
        else:
            raise AssertionError(path)


def test_pilot_lines_point_at_the_intended_code():
    """Every expected line and endpoint in pilot.yaml sits on the statement it names."""
    pilot = yaml.safe_load((ROOT / "experiments/provider_reach/pilot.yaml").read_text())
    for fid, fixture in pilot["fixtures"].items():
        repo = ROOT / fixture["repo"]
        if not repo.exists():
            pytest.skip(f"{repo} not built")
        git = GitRepo(repo)
        commit = git.resolve(fixture["commits"]["base"])
        checks = [(e["file"], e["line"], e["contains"]) for e in fixture["expect_lines"]]
        checks += [(e["file"], e["line"], e["name"]) for e in fixture["endpoints"]["base"].values()]
        for file, n, text in checks:
            assert text in git.read_blob(commit, file).decode().splitlines()[n - 1], (fid, file, n)
