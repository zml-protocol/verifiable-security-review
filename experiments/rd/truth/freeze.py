"""Truth-tooling production freeze: bind the reviewed tools to frozen inputs (PREREGISTRATION §15).

This wires the already-reviewed truth tooling to its frozen inputs and records one provenance
manifest. It writes **no fixture truth** and reads no advisory or fixture source; it only pins
hashes and re-checks invariants. Run it after the selection queue is frozen and before any
fixture-specific truth work.

Binds / pins:
- the single frozen anchor matcher (``matcher.node_identity``) via its provenance manifest;
- the frozen admissible vocabulary: 9 relation groups, qualifier kinds ``guard/config/dispatch_target``
  (``transform`` is a vocabulary blind spot), entry/behavior fixed;
- the frozen provider-support table;
- the frozen selection queue (``results/rd-queue.yaml``) with its hash and the log head;
- the truth-tooling source hashes.

Re-checks (fail loud otherwise): matcher provenance; vocabulary gate READY; queue hash == the
log's ``queue`` entry; the behavioural rules of the reviewed tools (via their self-tests); the four
truth statuses stay independent; ``NA`` is a structural string value, not 0; and the designated
truth-write area excludes ``results/`` and the selection artifacts.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
TRUTH_DIR = HERE.parent
REPO = HERE.parents[3]
RESULTS = REPO / "results"
VOCABULARY = RESULTS / "rd-vocabulary.json"
QUEUE = RESULTS / "rd-queue.yaml"
LOG = RESULTS / "rd-selection-log.jsonl"
POOL = RESULTS / "rd-candidate-pool.json"
FREEZE_MANIFEST = TRUTH_DIR / "truth-tooling-freeze.json"

# Fixture truth may be written ONLY under here; never under results/ or the selection run tree.
DESIGNATED_TRUTH_DIR = TRUTH_DIR / "fixtures"
FORBIDDEN_WRITE_ROOTS = (RESULTS.resolve(), (REPO / "runs" / "rd" / "selection").resolve())

EXPECTED_RELATION_GROUPS = 9
EXPECTED_QUALIFIERS = ("guard", "config", "dispatch_target")

# Truth-tooling sources whose hashes are pinned at freeze.
TOOL_SOURCES = (
    "experiments/rd/truth/matcher.py",
    "experiments/rd/truth/goresolver/node_id.go",
    "experiments/rd/truth/goresolver/go.mod",
    "experiments/rd/truth/resolver.py",
    "experiments/rd/truth/revision_map.py",
    "experiments/rd/truth/anchor_machinery.py",
    "experiments/rd/truth/agreement.py",
    "experiments/rd/truth/distractors.py",
    "experiments/rd/truth/negative_control.py",
    "experiments/rd/truth/templates.py",
    "experiments/rd/truth/vocabulary.py",
    "experiments/rd/truth/freeze.py",
    "experiments/rd/agent/phases.py",
    "experiments/rd/agent/verifiability.py",
)


class FreezeError(RuntimeError):
    """A truth-tooling freeze invariant failed (fail loud)."""


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _import(name: str):
    sys.path.insert(0, str(TRUTH_DIR))
    sys.path.insert(0, str(REPO / "experiments" / "rd" / "agent"))
    return __import__(name)


def truth_artifact_path(fixture_id: str, name: str) -> Path:
    """Resolve a fixture-truth artifact path and refuse anything outside the designated area or
    inside results/ or the selection run tree. (Used by later fixture-truth work; not now.)"""
    if "/" in fixture_id or "\\" in fixture_id or fixture_id in ("", ".", ".."):
        raise FreezeError(f"unsafe fixture id: {fixture_id!r}")
    candidate = (DESIGNATED_TRUTH_DIR / fixture_id / name).resolve()
    if DESIGNATED_TRUTH_DIR.resolve() not in candidate.parents:
        raise FreezeError(f"refusing to write truth outside the designated area: {candidate}")
    for bad in FORBIDDEN_WRITE_ROOTS:
        if bad == candidate or bad in candidate.parents:
            raise FreezeError(f"refusing to write truth under a protected tree: {candidate}")
    return candidate


def _check_vocabulary() -> dict:
    vocab = _import("vocabulary")
    if not VOCABULARY.exists():
        raise FreezeError(f"missing frozen vocabulary: {VOCABULARY}")
    doc = json.loads(VOCABULARY.read_text())
    if doc.get("gate_status") != "READY":
        raise FreezeError(f"vocabulary gate is {doc.get('gate_status')!r}, not READY")
    relations = [k for k in doc.get("truth_vocabulary", {}) if "/" in k]
    if len(relations) != EXPECTED_RELATION_GROUPS:
        raise FreezeError(f"expected {EXPECTED_RELATION_GROUPS} relation groups, found {len(relations)}")
    if tuple(vocab.allowed_qualifier_kinds()) != EXPECTED_QUALIFIERS:
        raise FreezeError(f"admissible qualifiers {vocab.allowed_qualifier_kinds()} != {EXPECTED_QUALIFIERS}")
    if vocab.is_admissible("transform"):
        raise FreezeError("transform must be a vocabulary blind spot, not admissible")
    return {"file_sha256": _sha256(VOCABULARY), "gate_status": "READY",
            "relation_groups": sorted(relations), "admissible_qualifiers": list(EXPECTED_QUALIFIERS),
            "provider_support_rows": sorted(doc.get("provider_support", {}))}


def _check_queue() -> dict:
    if not QUEUE.exists():
        raise FreezeError("selection queue is not frozen (results/rd-queue.yaml missing)")
    import yaml
    q = yaml.safe_load(QUEUE.read_text())
    entries = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
    queue_entry = [e for e in entries if e.get("step") == "queue"]
    if len(queue_entry) != 1:
        raise FreezeError(f"expected exactly one queue log entry, found {len(queue_entry)}")
    qh = _sha256(QUEUE)
    if queue_entry[0].get("queue_sha256") != qh:
        raise FreezeError("rd-queue.yaml hash does not match the log's queue entry")
    if q.get("log_head") != entries[-2]["hash"]:
        raise FreezeError("queue.log_head is not the pre-queue log tip")
    return {"queue_sha256": qh, "log_head": q.get("log_head"), "log_tip": entries[-1]["hash"],
            "n": q.get("n")}


def _check_tool_rules() -> dict:
    """Run the reviewed tools' own self-tests as behavioural gates (fixture-free, fast)."""
    templates = _import("templates")
    # four truth statuses independent; NA is a structural string, not 0
    if len(set(templates.TRUTH_STATUSES)) != 4:
        raise FreezeError("the four truth statuses are not independent")
    if "NA" not in templates.STATE_VALUES or 0 in templates.STATE_VALUES:
        raise FreezeError("NA must be a structural string value, not numeric 0")
    ran = []
    for name in ("agreement", "distractors", "negative_control"):
        mod = _import(name)
        fn = getattr(mod, "self_test", None) or getattr(mod, "_self_test", None)
        if fn is None:
            raise FreezeError(f"{name} has no self-test to gate on")
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
        ran.append(name)
    return {"self_tests_passed": ran,
            "truth_statuses": list(templates.TRUTH_STATUSES),
            "state_values": list(templates.STATE_VALUES)}


def _check_selection() -> dict:
    """Pin the candidate pool hash and the selection seed: the revision A/B mapping derives from the
    seed and reads the pool, so both must be frozen or that mapping could silently change."""
    if not POOL.exists():
        raise FreezeError(f"missing candidate pool: {POOL}")
    doc = json.loads(POOL.read_text())
    return {"pool_sha256": _sha256(POOL), "seed": int(doc["seed"])}


def build_freeze() -> dict:
    matcher = _import("matcher")
    matcher.check_provenance()  # fail loud if the matcher drifted
    manifest = {
        "frozen_at_rule": "PREREGISTRATION.md §15 (truth tooling production freeze)",
        "matcher": {"spec": matcher.FROZEN_SPEC, "provenance": str(matcher.MANIFEST.relative_to(REPO)),
                    "matcher_sha256": _sha256(matcher.HERE)},
        "vocabulary": _check_vocabulary(),
        "queue": _check_queue(),
        "selection": _check_selection(),
        "tool_rules": _check_tool_rules(),
        "tool_source_sha256": {src: _sha256(REPO / src) for src in TOOL_SOURCES},
        "designated_truth_dir": str(DESIGNATED_TRUTH_DIR.relative_to(REPO)),
        "forbidden_write_roots": [str(p.relative_to(REPO)) for p in FORBIDDEN_WRITE_ROOTS],
    }
    return manifest


def write_freeze() -> dict:
    doc = build_freeze()
    FREEZE_MANIFEST.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def verify_freeze() -> dict:
    """Re-check every pinned input against the written freeze manifest (fail loud)."""
    if not FREEZE_MANIFEST.exists():
        raise FreezeError(f"missing freeze manifest: {FREEZE_MANIFEST}")
    pinned = json.loads(FREEZE_MANIFEST.read_text())
    live = build_freeze()
    for src, want in pinned["tool_source_sha256"].items():
        if live["tool_source_sha256"].get(src) != want:
            raise FreezeError(f"{src} changed since the truth-tooling freeze")
    if live["matcher"]["matcher_sha256"] != pinned["matcher"]["matcher_sha256"]:
        raise FreezeError("matcher changed since the truth-tooling freeze")
    if live["queue"]["queue_sha256"] != pinned["queue"]["queue_sha256"]:
        raise FreezeError("selection queue changed since the truth-tooling freeze")
    if live["vocabulary"]["file_sha256"] != pinned["vocabulary"]["file_sha256"]:
        raise FreezeError("vocabulary changed since the truth-tooling freeze")
    sel_live, sel_pin = live.get("selection", {}), pinned.get("selection", {})
    if sel_live.get("pool_sha256") != sel_pin.get("pool_sha256"):
        raise FreezeError("candidate pool changed since the truth-tooling freeze (A/B mapping would drift)")
    if sel_live.get("seed") != sel_pin.get("seed"):
        raise FreezeError("selection seed changed since the truth-tooling freeze")
    return pinned


def _self_test() -> None:
    # The write-area guard refuses results/ and the selection tree, and accepts the designated area.
    ok = truth_artifact_path("GHSA-xxxx", "truth.yaml")
    assert DESIGNATED_TRUTH_DIR.resolve() in ok.parents
    for bad_id in ("..", "a/b"):
        try:
            truth_artifact_path(bad_id, "t.yaml")
        except FreezeError:
            pass
        else:
            raise AssertionError(f"unsafe fixture id accepted: {bad_id}")
    doc = build_freeze()
    assert doc["vocabulary"]["admissible_qualifiers"] == list(EXPECTED_QUALIFIERS)
    assert len(doc["vocabulary"]["relation_groups"]) == EXPECTED_RELATION_GROUPS
    assert doc["queue"]["n"] == {"go": 6, "python": 6}
    print("freeze self-test ok:", {"relations": len(doc["vocabulary"]["relation_groups"]),
                                    "qualifiers": doc["vocabulary"]["admissible_qualifiers"],
                                    "queue_n": doc["queue"]["n"],
                                    "self_tests": doc["tool_rules"]["self_tests_passed"]})


if __name__ == "__main__":
    if "--write" in sys.argv:
        print(json.dumps(write_freeze(), indent=2))
    elif "--verify" in sys.argv:
        verify_freeze()
        print("truth-tooling freeze verified")
    elif "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
