"""Expected answers per metamorphic condition, derived from one golden file."""

from __future__ import annotations

from .derive import attribute, revision_status
from .models import Fact, Golden, GoldenHypothesis

# For each condition: which original side plays (base, head).
SOURCES = {
    "forward": ("base", "head"),
    "swapped": ("head", "base"),
    "identity_base": ("base", "base"),
    "identity_head": ("head", "head"),
}


def expected(g: GoldenHypothesis, condition: str) -> dict:
    src = dict(zip(("base", "head"), SOURCES[condition]))
    comps = {side: {c: g.components[c][src[side]] for c in g.components} for side in src}
    rev = {side: revision_status(comps[side]) for side in src}
    implicated = condition in ("forward", "swapped") and g.attribution["static_only"] in (
        "CHANGE_IMPLICATED",
        "FIX_IMPLICATED",
    )
    # A fact about an original side applies to whichever side(s) now show that commit.
    facts = [
        Fact(**{**f.model_dump(), "id": f"{f.id}@{side}", "revision": side})
        for f in g.facts
        for side in src
        if src[side] == f.revision
    ]
    return {
        "components": comps,
        "revisions": rev,
        "attribution": attribute(rev["base"], rev["head"], implicated),
        "facts": facts,
    }


def check_golden(golden: Golden) -> list[str]:
    """A golden's stated attribution must follow from its own component table."""
    problems = []
    for hid, g in golden.hypotheses.items():
        got = expected(g, "forward")["attribution"]
        if got != g.attribution["static_only"]:
            problems.append(
                f"golden {golden.case}/{hid}: components imply {got}, "
                f"file says {g.attribution['static_only']}"
            )
    return problems
