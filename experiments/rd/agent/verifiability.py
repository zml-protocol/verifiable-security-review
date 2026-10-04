"""B-phase verifiability gate from the frozen provider-support table (PREREGISTRATION.md §15).

This is the one piece of the scaffold that reads ``provider_support`` from
``results/rd-vocabulary.json``. It is deliberately a **separate module** so that phase A
(`phases.PhaseA`) never imports or reaches it: requirement discovery must not be shaped by what a
verifier can express. Phase B imports it; phase A does not.

Frozen B-phase rule (verbatim in the vocabulary file, key ``b_phase``):

    SUPPORTED and PARTIAL verifiers make hops of their relation-language pair machine-verifiable.
    For UNSUPPORTED and NON_CONFORMANT pairs an agent may still state the relation, but the system
    only ever marks it unsupported / unverified, never VERIFIED. Agents learn only whether a pair is
    verifiable, not the synthetic blind spots.

So this module exposes **only a boolean** per (language, relation) pair. It never returns status
strings, blind spots or disagreements — the agent learns verifiable-or-not, nothing more.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VOCABULARY = ROOT / "results" / "rd-vocabulary.json"

# Only these provider-support statuses yield a machine-verifiable (VERIFIED-eligible) pair.
VERIFIABLE_STATUSES = frozenset({"SUPPORTED", "PARTIAL"})
# Stated here for completeness; these can be proposed by an agent but are never VERIFIED.
UNVERIFIABLE_STATUSES = frozenset({"UNSUPPORTED", "NON_CONFORMANT"})


def _provider_support() -> dict:
    if not VOCABULARY.exists():
        raise SystemExit(f"missing frozen vocabulary: {VOCABULARY}")
    doc = json.loads(VOCABULARY.read_text())
    if doc.get("gate_status") != "READY":
        raise SystemExit(f"conformance gate is {doc.get('gate_status')!r}: gate refuses to run")
    table = doc.get("provider_support") or {}
    if not isinstance(table, dict):
        raise SystemExit("provider_support is not a mapping")
    return table


def _status_for(language: str | None, relation: str | None) -> str | None:
    """Look up the pair's status. Keys are ``<verifier>/<language>/<relation>``; the frozen table
    has a single verifier (codeql), so a (language, relation) pair maps to at most one row."""
    if not language or not relation:
        return None
    table = _provider_support()
    suffix = f"/{language}/{relation}"
    matches = {k: v["status"] for k, v in table.items() if k.endswith(suffix)}
    if len(matches) > 1:
        # Ambiguous across verifiers: never silently pick one.
        raise SystemExit(f"provider_support has multiple verifiers for {language}/{relation}: {sorted(matches)}")
    return next(iter(matches.values()), None)


def verifiable_pair(language: str | None, relation: str | None) -> bool:
    """True iff the (language, relation) pair is machine-verifiable (status SUPPORTED or PARTIAL).

    An unknown pair, or one with an unverifiable status, is False. This is the ONLY fact the B
    phase may learn about provider support — no status string, no blind spots.
    """
    return _status_for(language, relation) in VERIFIABLE_STATUSES


def _self_test() -> None:
    table = _provider_support()
    # Every frozen row is either verifiable or not, consistently with its status.
    for key, row in table.items():
        parts = key.split("/")
        assert len(parts) == 3, f"unexpected key shape: {key}"
        _verifier, lang, rel = parts
        want = row["status"] in VERIFIABLE_STATUSES
        assert verifiable_pair(lang, rel) == want, key
    # An unknown pair is not verifiable.
    assert verifiable_pair("go", "no_such_relation") is False
    assert verifiable_pair(None, None) is False
    verifiable = sorted(k for k, v in table.items() if v["status"] in VERIFIABLE_STATUSES)
    print("verifiability self-test ok:", {"verifiable_pairs": len(verifiable), "rows": len(table)})


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
