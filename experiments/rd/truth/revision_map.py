"""Frozen per-fixture revision mapping (PREREGISTRATION §15.5).

Author truth is written with canonical slot keys ``vuln`` / ``fixed`` (unambiguous: which revision is
the vulnerable/parent one and which is the fixed one). The agent/scorer slot keys ``revision_A`` /
``revision_B`` are assigned ONCE per fixture by a deterministic function of the frozen selection seed,
so that before/after identity is not exposed by the A/B label and the assignment can never be
silently remapped a second time. Entry/behavior/qualifier anchors, present/absent states and the
scorer therefore all share one A/B assignment.

`vuln`/`fixed` is the internal canonical labeling; `revision_A`/`revision_B` is the frozen outward
labeling. This module maps the former to the latter and refuses to touch an already-mapped doc.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
POOL = REPO / "results" / "rd-candidate-pool.json"
FREEZE_MANIFEST = Path(__file__).resolve().parent / "truth-tooling-freeze.json"

CANONICAL = ("vuln", "fixed")
OUTWARD = ("revision_A", "revision_B")


class RevisionMapError(RuntimeError):
    pass


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _seed() -> int:
    """Return the frozen selection seed, after binding it to the frozen pool provenance.

    The A/B mapping derives from (seed, fixture_id) and the seed lives in the candidate pool, so the
    mapping is only reproducible if the pool is the one pinned at the truth-tooling freeze. Drift in
    either the pool hash or the seed fails loud rather than silently remapping revisions."""
    if not FREEZE_MANIFEST.exists():
        raise RevisionMapError(f"missing truth-tooling freeze manifest: {FREEZE_MANIFEST}")
    sel = (json.loads(FREEZE_MANIFEST.read_text()) or {}).get("selection")
    if not sel or "pool_sha256" not in sel or "seed" not in sel:
        raise RevisionMapError("freeze manifest has no pinned selection pool_sha256/seed")
    if not POOL.exists():
        raise RevisionMapError(f"missing candidate pool: {POOL}")
    if _sha256(POOL) != sel["pool_sha256"]:
        raise RevisionMapError("candidate pool changed since the truth freeze; A/B mapping refused")
    live_seed = int(json.loads(POOL.read_text())["seed"])
    if live_seed != int(sel["seed"]):
        raise RevisionMapError("selection seed changed since the truth freeze; A/B mapping refused")
    return int(sel["seed"])


def seed_revision_map(fixture_id: str) -> dict:
    """Deterministic, frozen assignment of outward A/B to canonical vuln/fixed for one fixture.

    Returns e.g. {"revision_A": "vuln", "revision_B": "fixed"} or the swap. Parity of a seeded hash
    decides, so across fixtures A is sometimes vuln and sometimes fixed."""
    h = hashlib.sha256(f"{_seed()}:{fixture_id}".encode()).hexdigest()
    swap = int(h[:8], 16) & 1  # 0 -> A=vuln, 1 -> A=fixed
    if swap:
        return {"revision_A": "fixed", "revision_B": "vuln"}
    return {"revision_A": "vuln", "revision_B": "fixed"}


def canonical_to_outward(fixture_id: str) -> dict:
    """Inverse view: canonical -> outward slot key for this fixture."""
    m = seed_revision_map(fixture_id)
    return {m["revision_A"]: "revision_A", m["revision_B"]: "revision_B"}


def make_source_provider(fixture_id: str, canonical_source):
    """Build the outward source provider the resolver/machinery need, keyed by the FROZEN mapping.

    `canonical_source(role, file) -> str` returns the file text at the canonical revision role
    ('vuln'|'fixed'). The returned `provider(outward_rev, file)` reads the source of whichever
    canonical role `outward_rev` maps to — so a fixed-side anchor always resolves against the fixed
    source even when the seed put `fixed` on `revision_A`. This closes the label/source desync."""
    m = seed_revision_map(fixture_id)  # {revision_A: 'vuln'|'fixed', revision_B: ...}

    def provider(outward_rev: str, file: str) -> str:
        if outward_rev not in OUTWARD:
            raise RevisionMapError(f"unknown outward revision {outward_rev!r}")
        return canonical_source(m[outward_rev], file)

    return provider


def _is_canonical_slot(value) -> bool:
    return isinstance(value, dict) and bool(set(value) & set(CANONICAL))


def _is_outward_slot(value) -> bool:
    return isinstance(value, dict) and bool(set(value) & set(OUTWARD))


def map_doc(doc: dict, fixture_id: str) -> dict:
    """Return a copy of a canonical (vuln/fixed-keyed) truth doc with slots relabeled to the frozen
    outward revision_A/revision_B. Refuses a doc that already carries outward keys (no second remap)."""
    c2o = canonical_to_outward(fixture_id)
    out = copy.deepcopy(doc)

    def relabel(container: dict) -> None:
        for value in container.values():
            if _is_outward_slot(value):
                raise RevisionMapError("doc already uses revision_A/revision_B; refusing a second remap")
            if _is_canonical_slot(value):
                unknown = set(value) - set(CANONICAL)
                if unknown:
                    raise RevisionMapError(f"slot has non-canonical keys {sorted(unknown)}")
                value_copy = {c2o[k]: v for k, v in value.items()}
                value.clear()
                value.update(value_copy)

    for item in out.get("items", []) or []:
        if isinstance(item, dict):
            relabel(item)
    for m in out.get("missing", []) or []:
        if isinstance(m, dict):
            relabel(m)
    return out


def _self_test() -> None:
    # deterministic
    assert seed_revision_map("GHSA-fq2j-j8hc-8vw8") == seed_revision_map("GHSA-fq2j-j8hc-8vw8")
    # both assignments occur across fixtures (not always A=vuln)
    roles = {seed_revision_map(fid)["revision_A"] for fid in
             ("GHSA-fq2j-j8hc-8vw8", "GHSA-hx8v-g79f-8w5f", "PYSEC-2026-1868", "GHSA-xmfj-7pp5-fxr6",
              "GO-2026-6237", "GHSA-rmrf-g9r3-73pm", "GHSA-5gfj-64gh-mgmw", "GHSA-937x-gpqr-72gg")}
    assert roles == {"vuln", "fixed"}, f"seed mapping is degenerate: {roles}"
    # map a canonical doc; one remap only
    item = {"id": "b", "kind": "behavior",
            "behavior": {"vuln": {"state": "absent", "context": {"file": "x", "start_line": 1, "end_line": 1, "expression": "a"}},
                         "fixed": {"state": "present", "anchor": {"file": "x", "start_line": 1, "end_line": 1, "expression": "b"}}}}
    mapped = map_doc({"items": [item]}, "GHSA-fq2j-j8hc-8vw8")
    slot = mapped["items"][0]["behavior"]
    assert set(slot) == set(OUTWARD)
    m = seed_revision_map("GHSA-fq2j-j8hc-8vw8")
    # the fixed-side anchor landed on whichever outward key maps to 'fixed'
    fixed_key = "revision_A" if m["revision_A"] == "fixed" else "revision_B"
    assert slot[fixed_key]["state"] == "present"
    # a second remap is refused
    try:
        map_doc(mapped, "GHSA-fq2j-j8hc-8vw8")
        raise AssertionError("second remap was not refused")
    except RevisionMapError:
        pass

    # Integration: the source provider must read the FIXED source for whichever outward key maps to
    # 'fixed' — label and source stay in sync. Use a fixture whose seed puts fixed on revision_A.
    import resolver
    fid = next(f for f in ("GHSA-fq2j-j8hc-8vw8", "GHSA-hx8v-g79f-8w5f", "GO-2026-6237",
                           "PYSEC-2026-1868", "GHSA-rmrf-g9r3-73pm")
               if seed_revision_map(f)["revision_A"] == "fixed")
    fixed_src = "package p\nfunc F() {\n\tsafe := true\n}\n"   # 'safe := true' exists only in fixed
    vuln_src = "package p\nfunc F() {\n\tx := 1\n}\n"
    canonical = {"fixed": fixed_src, "vuln": vuln_src}
    provider = make_source_provider(fid, lambda role, f: canonical[role])
    marker = {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "safe := true"}
    # revision_A -> fixed here, so the marker resolves from the source the provider returns for A
    ident_a = resolver.resolve_identity(marker, language="go", revision="revision_A",
                                        source=provider("revision_A", "p.go"))
    assert ident_a[1] == "revision_A"
    # the other outward key maps to vuln, whose source lacks the marker -> fail loud
    try:
        resolver.resolve_identity(marker, language="go", revision="revision_B",
                                  source=provider("revision_B", "p.go"))
        raise AssertionError("marker wrongly resolved against the vuln source")
    except resolver.ResolverError:
        pass
    print("revision_map self-test ok:", {"seed": _seed(), "map": m, "fixed_on": "revision_A", "fixture": fid})


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
