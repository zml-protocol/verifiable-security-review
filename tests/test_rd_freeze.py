"""Hard gates for the truth-tooling production freeze (experiments/rd/truth/freeze.py).

Verifies the freeze binds and re-checks its frozen inputs, that a drifted tool source is refused,
and that the designated truth-write area excludes results/ and the selection artifacts. Writes no
fixture truth.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
import freeze  # noqa: E402


def test_freeze_verifies_against_frozen_inputs():
    pinned = freeze.verify_freeze()
    assert pinned["vocabulary"]["gate_status"] == "READY"
    assert len(pinned["vocabulary"]["relation_groups"]) == freeze.EXPECTED_RELATION_GROUPS
    assert tuple(pinned["vocabulary"]["admissible_qualifiers"]) == freeze.EXPECTED_QUALIFIERS
    assert pinned["queue"]["n"] == {"go": 6, "python": 6}
    assert pinned["tool_rules"]["self_tests_passed"] == ["agreement", "distractors", "negative_control"]


def test_truth_statuses_independent_and_na_structural():
    doc = freeze.build_freeze()
    assert len(set(doc["tool_rules"]["truth_statuses"])) == 4
    assert "NA" in doc["tool_rules"]["state_values"] and 0 not in doc["tool_rules"]["state_values"]


def test_write_area_guard_excludes_protected_trees():
    ok = freeze.truth_artifact_path("GHSA-abc", "truth.yaml")
    assert freeze.DESIGNATED_TRUTH_DIR.resolve() in ok.parents
    # results/ and the selection tree are never under the designated area
    assert freeze.RESULTS.resolve() not in freeze.DESIGNATED_TRUTH_DIR.resolve().parents
    for bad in ("..", "a/b", "", "."):
        with pytest.raises(freeze.FreezeError):
            freeze.truth_artifact_path(bad, "t.yaml")


def test_drifted_tool_source_refused(tmp_path, monkeypatch):
    pinned = json.loads(freeze.FREEZE_MANIFEST.read_text())
    pinned["tool_source_sha256"]["experiments/rd/truth/agreement.py"] = "0" * 64
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(pinned))
    monkeypatch.setattr(freeze, "FREEZE_MANIFEST", p)
    with pytest.raises(freeze.FreezeError):
        freeze.verify_freeze()


def test_drifted_matcher_refused(tmp_path, monkeypatch):
    pinned = json.loads(freeze.FREEZE_MANIFEST.read_text())
    pinned["matcher"]["matcher_sha256"] = "0" * 64
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(pinned))
    monkeypatch.setattr(freeze, "FREEZE_MANIFEST", p)
    with pytest.raises(freeze.FreezeError):
        freeze.verify_freeze()
