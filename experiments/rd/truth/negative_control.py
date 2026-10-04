"""Negative-control claim selection (PREREGISTRATION.md §15.6). DRAFT — pending Codex review.

For a fixture whose CWE is ``c``, walk the frozen substitution list L from the position after
``c``, cyclically, skip entries in the same CWE class as ``c``, and return the first ``n``
candidates. The first candidate that the author and both adjudicators agree is
"not supported at either revision" becomes the fixture's negative control; if none of the ``n``
reaches three-way agreement, the fixture has no negative control and reports so.

The class map is imported from the frozen ``selection.py`` so this file cannot drift from §15.2.

    uv run python experiments/rd/truth/negative_control.py --cwe 918
    uv run python experiments/rd/truth/negative_control.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # experiments/rd


def _class_map() -> dict:
    """The frozen §15.2 class map, reached only through the selection provenance gate.

    ``checked()`` verifies the script hash against the pool's ``script_sha256``, the pool hash
    against the log, and the log's hash chain; drift exits with SELECTION_PROTOCOL_CHANGED rather
    than letting a modified class map leak into the truth phase.
    """
    try:
        from selection import CWE_CLASS_OF, checked
    except Exception as exc:  # pragma: no cover - environment problem, not a cwe property
        raise SystemExit(
            f"cannot import the frozen selection module: {exc}. "
            "Run with `uv run python ...` from the repository root."
        ) from exc
    checked()
    return CWE_CLASS_OF


CWE_CLASS_OF = _class_map()

# Frozen order, §15.6. Do not edit.
CWE_LIST = [22, 79, 89, 78, 287, 862, 918, 502, 601, 611, 400, 352]


def cwe_class(cwe: int) -> str:
    return CWE_CLASS_OF.get(cwe, f"CWE-{cwe}")


def candidates(cwe: int, n: int = 3) -> list[int]:
    """The first ``n`` substitution candidates for a fixture CWE, in frozen cyclic order."""
    if n < 1:
        raise ValueError("n must be >= 1")
    try:
        start = CWE_LIST.index(cwe) + 1
    except ValueError:
        start = 0  # c not in L: start from the beginning
    out: list[int] = []
    own_class = cwe_class(cwe)
    for offset in range(len(CWE_LIST)):
        candidate = CWE_LIST[(start + offset) % len(CWE_LIST)]
        if candidate == cwe or cwe_class(candidate) == own_class:
            continue
        out.append(candidate)
        if len(out) == n:
            break
    return out


def self_test() -> None:
    cases = {
        918: [502, 601, 611],   # ssrf -> deserialization, open-redirect, xxe
        22: [79, 89, 78],       # path traversal -> xss, sqli, cmdi
        352: [22, 79, 89],      # csrf is last -> wrap
        20: [22, 79, 89],       # unlisted cwe -> from the start
    }
    for cwe, expected in cases.items():
        got = candidates(cwe)
        assert got == expected, f"CWE-{cwe}: expected {expected}, got {got}"
    # the class check is real: the only multi-member class inside L is injection (78, 89)
    assert CWE_CLASS_OF.get(78) == CWE_CLASS_OF.get(89) == "injection"
    picked78 = candidates(78, n=len(CWE_LIST) - 1)
    picked89 = candidates(89, n=len(CWE_LIST) - 1)
    assert 89 not in picked78 and 78 not in picked89, (picked78, picked89)
    # every picked candidate must differ from the fixture's class
    for cwe in (22, 78, 89, 918, 352, 20):
        for candidate_cwe in candidates(cwe, n=len(CWE_LIST) - 1):
            assert cwe_class(candidate_cwe) != cwe_class(cwe) or candidate_cwe == cwe, (cwe, candidate_cwe)
    print("negative_control self-test OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cwe", type=int)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if args.cwe is None:
        ap.error("--cwe or --self-test is required")
    picked = candidates(args.cwe, args.n)
    print({"cwe": args.cwe, "class": cwe_class(args.cwe), "candidates": picked})


if __name__ == "__main__":
    main()
