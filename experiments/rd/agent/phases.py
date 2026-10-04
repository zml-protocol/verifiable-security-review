"""RD agent protocol / scorer scaffold: phases A, B, C (PREREGISTRATION.md §15).

Fixture-free skeleton. It fixes the *shape* and the *invariants* of the three phases; it holds no
candidate-specific value, reads no fixture, advisory or selection log, and writes nothing under
``results/``. The actual discovery/realization/attribution logic is the agent's work at fixture
time and is deliberately not implemented here.

Phases and their hard invariants:

- **A — requirement discovery.** The agent states the requirement items of a fixture. Admissible
  item kinds are the two fixed requirement kinds (``entry``, ``behavior``) plus the frozen
  admissible qualifier kinds, sourced from ``truth/vocabulary.py`` (never hardcoded). A ``transform``
  item is recorded but classified ``UNSUPPORTED_REQUIREMENT_TYPE`` — a vocabulary blind spot — and
  never occupies a normal qualifier slot. (A *changed transform* may still be named as the
  ``behavior``; that is a behavior item, not a transform qualifier.) Phase A has **no access to
  provider-support**: it cannot import or reach the verifiability gate.

- **B — realization.** Consumes a **locked** A (sealed by content hash; a mutated A fails loud).
  Attaches realizations whose anchors/contexts come from fixture-time callbacks — the scaffold
  never fabricates them. B consults the provider-support B-phase gate (``verifiability.py``) to mark
  each relation-bearing hop VERIFIED-eligible or unverified. **B cannot modify A.**

- **C — attribution.** Consumes a **frozen** A and a **frozen** B only. **C cannot modify A or B.**

Report wording for admissibility statements is fixed: ``REPORT_PHRASE``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Reuse the frozen vocabulary accessor rather than re-declaring the tables.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "truth"))
import vocabulary  # noqa: E402  (experiments/rd/truth/vocabulary.py)

REPORT_PHRASE = "within the admissible RD vocabulary"

REQUIREMENT_FIXED = vocabulary.REQUIREMENT_FIXED  # ("entry", "behavior")
# transform is the sole universe member that exited the vocabulary; it is a blind spot, never a slot.
VOCABULARY_BLIND_SPOT_KINDS = tuple(
    k for k in vocabulary.QUALIFIER_UNIVERSE if k not in vocabulary.allowed_qualifier_kinds()
)

# Independent, non-collapsing status constants (kept distinct per §15.1/§15.4).
UNSUPPORTED_REQUIREMENT_TYPE = "UNSUPPORTED_REQUIREMENT_TYPE"


class PhaseError(RuntimeError):
    """A phase invariant was violated (fail loud; never silently repaired)."""


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _seal(obj) -> str:
    return hashlib.sha256(_canonical(obj).encode()).hexdigest()


def classify_requirement_kind(kind: str) -> str:
    """Return the admissible slot kind, or UNSUPPORTED_REQUIREMENT_TYPE for a blind-spot kind.

    `entry`/`behavior` and the frozen admissible qualifier kinds classify as themselves; `transform`
    (and any other universe member that exited the vocabulary) classifies as the blind-spot status.
    An entirely unknown token is also UNSUPPORTED_REQUIREMENT_TYPE (never invented into the vocab).
    """
    if kind in REQUIREMENT_FIXED or kind in vocabulary.allowed_qualifier_kinds():
        return kind
    return UNSUPPORTED_REQUIREMENT_TYPE


# The structured requirement payload a phase-A item carries, by kind. The A seal covers ALL of it,
# so phase B/C cannot change a requirement's substance (anchors, expected field, per-revision state,
# rationale, or an unsupported-type proposal) without the seal detecting it. Shapes (the scaffold
# seals whatever is supplied; a fixture-time validator will enforce these precisely later):
#   entry / behavior : {"anchor": <node ref>, "rationale": <str?>}
#   guard/config/dispatch_target (qualifier): {"subject_anchor": <node ref>,
#       "expected_semantic_field": <value>, "state": {"<rev>": {"state": "present"|"absent",
#       "anchor": <ref?>, "context": <ref?>}}, "rationale": <str?>}
#   transform / unknown : an UNSUPPORTED_REQUIREMENT_TYPE proposal, e.g.
#       {"proposed_kind": <str>, "rationale": <str?>, ...} — still sealed as part of the artifact.
# `rationale` is deliberately part of the seal (Codex): B/C must not be able to rewrite A's reasoning.
@dataclass(frozen=True)
class RequirementItem:
    """One phase-A item: a stated kind plus the full structured requirement `payload`. `slot` is the
    classified kind. The frozen dataclass pins the (local_id, kind) binding; `payload` is a deep copy
    owned by phase A (so a caller mutating the dict they passed cannot reach the sealed artifact),
    and the seal is taken over `public()`, which includes the whole payload."""

    local_id: str
    kind: str
    payload: dict = field(default_factory=dict)

    @property
    def slot(self) -> str:
        return classify_requirement_kind(self.kind)

    @property
    def is_blind_spot(self) -> bool:
        return self.slot == UNSUPPORTED_REQUIREMENT_TYPE

    def public(self) -> dict:
        # Live view: returns the owned payload object, so a post-lock nested mutation is visible to
        # the seal recomputation (and thus caught by _require_frozen / phase C).
        return {"local_id": self.local_id, "kind": self.kind, "slot": self.slot,
                "payload": self.payload}


class PhaseA:
    """Requirement discovery. Mutable until `lock()`, immutable (sealed) after."""

    def __init__(self) -> None:
        self._items: list[RequirementItem] = []
        self._sealed: str | None = None

    def add(self, local_id: str, kind: str, payload: dict | None = None) -> RequirementItem:
        if self._sealed is not None:
            raise PhaseError("phase A is locked; it cannot be modified")
        # Deep copy so the caller's dict/list objects are not shared with the sealed artifact.
        item = RequirementItem(local_id=local_id, kind=kind, payload=copy.deepcopy(payload or {}))
        self._items.append(item)
        return item

    def lock(self) -> str:
        """Freeze A and return its seal. Idempotent."""
        if self._sealed is None:
            self._sealed = _seal([i.public() for i in self._items])
        return self._sealed

    @property
    def seal(self) -> str:
        if self._sealed is None:
            raise PhaseError("phase A is not locked yet")
        return self._sealed

    def items(self) -> tuple[RequirementItem, ...]:
        return tuple(self._items)

    def report(self) -> dict:
        """Admissibility summary, phrased with the fixed REPORT_PHRASE."""
        self.lock()
        admissible = [i.public() for i in self._items if not i.is_blind_spot]
        blind = [i.public() for i in self._items if i.is_blind_spot]
        return {
            "phrase": REPORT_PHRASE,
            "seal": self._sealed,
            "admissible_items": admissible,
            "blind_spot_items": blind,  # UNSUPPORTED_REQUIREMENT_TYPE, reported, never scored as a slot
        }


def _require_frozen(phase_a: PhaseA) -> str:
    seal = phase_a.seal  # raises if not locked
    live = _seal([i.public() for i in phase_a.items()])
    if live != seal:
        raise PhaseError("phase A content changed after it was locked (seal mismatch); refusing")
    return seal


@dataclass
class Realization:
    """A phase-B realization of one admissible A item. Anchors/contexts are supplied, never minted
    here. `relation` and `language` (when present) drive the B-phase verifiability gate.

    This is the *caller input* type. On `PhaseB.realize()` it is deep-copied into B's internal
    record, so the caller mutating their original dict afterwards cannot change the frozen state.
    """

    item_local_id: str
    relation: str | None = None
    language: str | None = None
    # opaque, fixture-time payload (anchors/contexts); the scaffold does not inspect its contents.
    payload: dict = field(default_factory=dict)
    verifiable: bool | None = None  # set by PhaseB.realize via the gate; None until realized


class PhaseB:
    """Realization. Binds to a locked A; cannot modify A."""

    def __init__(self, phase_a: PhaseA, verifiability_gate) -> None:
        self._a_seal = _require_frozen(phase_a)
        self._a = phase_a
        self._gate = verifiability_gate  # callable(language, relation) -> bool (verifiable pair?)
        self._realizations: list[Realization] = []
        self._sealed: str | None = None
        self._admissible_ids = {i.local_id for i in phase_a.items() if not i.is_blind_spot}

    def realize(self, r: Realization) -> Realization:
        if self._sealed is not None:
            raise PhaseError("phase B is locked; it cannot be modified")
        _require_frozen(self._a)  # A must still match its seal on every B write
        if r.item_local_id not in self._admissible_ids:
            raise PhaseError(
                f"{r.item_local_id!r} is not an admissible phase-A item "
                "(unknown, or an UNSUPPORTED_REQUIREMENT_TYPE blind spot); cannot realize it"
            )
        verifiable = r.verifiable
        if r.relation is not None:
            # Verifiability is the ONLY thing the gate reveals (never the blind-spot content).
            verifiable = bool(self._gate(r.language, r.relation))
        # Snapshot: deep-copy the payload so the caller's later mutation of their dict cannot reach
        # the frozen state. The stored object is what the seal (and C's live re-check) hashes.
        stored = Realization(
            item_local_id=r.item_local_id,
            relation=r.relation,
            language=r.language,
            payload=copy.deepcopy(r.payload),
            verifiable=verifiable,
        )
        self._realizations.append(stored)
        return stored

    def _public(self) -> list[dict]:
        """Canonical, *live* content of B — includes payload. Recomputed on every call so a
        post-lock mutation of any stored realization is visible."""
        return [
            {"item": r.item_local_id, "relation": r.relation, "language": r.language,
             "payload": r.payload, "verifiable": r.verifiable}
            for r in self._realizations
        ]

    def _live_seal(self) -> str:
        return _seal({"a": self._a_seal, "b": self._public()})

    def lock(self) -> str:
        """Seal B's current content (idempotent: sets the seal once)."""
        if self._sealed is None:
            _require_frozen(self._a)
            self._sealed = self._live_seal()
        return self._sealed

    def require_frozen(self) -> str:
        """Fail loud unless B is locked AND its live content still matches the seal."""
        if self._sealed is None:
            raise PhaseError("phase B is not locked yet")
        if self._live_seal() != self._sealed:
            raise PhaseError("phase B content changed after it was locked (seal mismatch); refusing")
        _require_frozen(self._a)  # A, which B's seal binds, must also be unchanged
        return self._sealed

    @property
    def seal(self) -> str:
        if self._sealed is None:
            raise PhaseError("phase B is not locked yet")
        return self._sealed

    def realizations(self) -> tuple[Realization, ...]:
        return tuple(self._realizations)


class PhaseC:
    """Attribution. Consumes frozen A and frozen B; modifies neither."""

    def __init__(self, phase_a: PhaseA, phase_b: PhaseB) -> None:
        self._a_seal = _require_frozen(phase_a)
        self._b_seal = phase_b.lock()
        self._a = phase_a
        self._b = phase_b

    def inputs_frozen(self) -> bool:
        """Re-verify both upstream phases against their *live* content (fail loud otherwise)."""
        if _require_frozen(self._a) != self._a_seal:
            raise PhaseError("phase A changed under phase C")
        if self._b.require_frozen() != self._b_seal:
            raise PhaseError("phase B changed under phase C")
        return True

    def consume(self) -> dict:
        self.inputs_frozen()
        return {
            "phrase": REPORT_PHRASE,
            "a_seal": self._a_seal,
            "b_seal": self._b_seal,
            "items": [i.public() for i in self._a.items()],
            "realizations": [
                {"item": r.item_local_id, "relation": r.relation,
                 "language": r.language, "verifiable": r.verifiable}
                for r in self._b.realizations()
            ],
        }


def _self_test() -> None:
    import verifiability  # local import so phase A never transitively needs it

    gate = verifiability.verifiable_pair  # callable(language, relation) -> bool

    # Phase A: two fixed kinds, one admissible qualifier (full structured payload), one blind spot.
    a = PhaseA()
    a.add("r1", "entry", {"anchor": {"path": "m.py", "span": [1, 2]}, "rationale": "the entry point"})
    a.add("r2", "behavior", {"anchor": {"path": "m.py", "span": [5, 6]}})
    external = {"subject_anchor": {"path": "m.py", "span": [3, 3]}, "expected_semantic_field": "must_hold",
                "state": {"base": {"state": "absent", "context": {"span": [3, 3]}},
                          "head": {"state": "present", "anchor": {"span": [3, 3]}}},
                "rationale": "guards the path"}
    a.add("r3", "guard", external)
    tr = a.add("r4", "transform", {"proposed_kind": "transform", "rationale": "changed transform"})
    assert tr.is_blind_spot and tr.slot == UNSUPPORTED_REQUIREMENT_TYPE
    assert "payload" in tr.public()  # the unsupported proposal is sealed as part of the artifact
    assert not RequirementItem("x", "guard").is_blind_spot
    rep = a.report()
    assert rep["phrase"] == REPORT_PHRASE
    assert len(rep["admissible_items"]) == 3 and len(rep["blind_spot_items"]) == 1

    # External dict the caller still holds must not be able to change the sealed artifact.
    external["expected_semantic_field"] = "must_not_hold"
    assert _require_frozen(a) == a.seal, "caller's external dict leaked into the sealed phase A"

    # A is locked after report(); further mutation fails loud.
    try:
        a.add("r5", "entry")
    except PhaseError:
        pass
    else:
        raise AssertionError("locked phase A accepted a new item")

    # Post-lock nested mutation of a sealed item's payload is caught by the live recompute.
    a.items()[2].payload["expected_semantic_field"] = "must_not_hold"
    try:
        _require_frozen(a)
    except PhaseError:
        pass
    else:
        raise AssertionError("post-lock nested payload mutation of A was not caught")
    a.items()[2].payload["expected_semantic_field"] = "must_hold"  # restore
    assert _require_frozen(a) == a.seal

    # Phase B: realize admissible items; relation-bearing hop gets a verifiability verdict.
    b = PhaseB(a, gate)
    caller_payload = {"anchor": "orig"}
    r1_stored = b.realize(Realization("r1", payload=caller_payload))
    sup = b.realize(Realization("r2", relation="def_use", language="go"))      # SUPPORTED
    unk = b.realize(Realization("r3", relation="no_such_relation", language="go"))  # not a known pair
    assert sup.verifiable is True
    assert unk.verifiable is False
    # Caller mutating the ORIGINAL payload dict after realize must not reach the stored snapshot.
    caller_payload["anchor"] = "tampered"
    assert r1_stored.payload["anchor"] == "orig", "caller mutation leaked into the realization"
    # Cannot realize a blind-spot item.
    try:
        b.realize(Realization("r4"))
    except PhaseError:
        pass
    else:
        raise AssertionError("phase B realized an UNSUPPORTED_REQUIREMENT_TYPE item")
    b.lock()

    # Phase C: consumes frozen A/B.
    c = PhaseC(a, b)
    out = c.consume()
    assert out["a_seal"] == a.seal and out["b_seal"] == b.seal
    assert out["phrase"] == REPORT_PHRASE

    def _must_catch(label: str) -> None:
        try:
            c.inputs_frozen()
        except PhaseError:
            return
        raise AssertionError(f"phase C did not catch {label}")

    # Tamper detection: mutating A's private list after lock is caught on C re-check.
    a._items.append(RequirementItem("sneak", "entry"))
    _must_catch("a post-lock mutation of A")
    a._items.pop()
    c.inputs_frozen()  # restored

    # Tamper detection: mutating a locked B realization's payload is caught by C's live re-check.
    b.realizations()[0].payload["anchor"] = "elsewhere"
    _must_catch("a post-lock mutation of B.payload")
    b.realizations()[0].payload["anchor"] = "orig"
    c.inputs_frozen()  # restored

    # Tamper detection: flipping a locked B realization's verifiable is caught too.
    saved = b.realizations()[1].verifiable
    b.realizations()[1].verifiable = not saved
    _must_catch("a post-lock mutation of B.verifiable")
    b.realizations()[1].verifiable = saved
    c.inputs_frozen()  # restored

    print("phases self-test ok:",
          {"admissible_qualifiers": list(vocabulary.allowed_qualifier_kinds()),
           "blind_spot_kinds": list(VOCABULARY_BLIND_SPOT_KINDS),
           "report_phrase": REPORT_PHRASE})


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
