"""Runtime-side conclusions: component status → revision status → attribution.

These are the spike's pre-registered rules (PREREGISTRATION.md §1B). The agent
only supplies observations; everything here is deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from .linemap import LineMap
from .models import Observation, Side

ComponentStatus = Literal["supported", "contradicted", "conflicted", "no_evidence"]
RevisionStatus = Literal["SUPPORTED", "CONTRADICTED", "CONFLICTED", "INCOMPLETE", "NO_EVIDENCE"]
Attribution = Literal[
    "CHANGE_IMPLICATED", "FIX_IMPLICATED", "PRE_EXISTING", "NOT_SUPPORTED",
    "UNATTRIBUTED", "UNDETERMINED",
]  # fmt: skip


def component_status(
    observations: Iterable[Observation], side: Side, component: str
) -> ComponentStatus:
    stances = {
        o.stance
        for o in observations
        if o.revision == side and o.component == component and o.stance != "unclear"
    }
    if stances == {"supports"}:
        return "supported"
    if stances == {"contradicts"}:
        return "contradicted"
    return "conflicted" if stances else "no_evidence"


def revision_status(components: dict[str, ComponentStatus]) -> RevisionStatus:
    # The claim is a conjunction: one contradicted component sinks it.
    values = components.values()
    if "contradicted" in values:
        return "CONTRADICTED"
    if "conflicted" in values:
        return "CONFLICTED"
    if all(v == "supported" for v in values):
        return "SUPPORTED"
    return "INCOMPLETE" if "supported" in values else "NO_EVIDENCE"


def attribute(base: RevisionStatus, head: RevisionStatus, implicated: bool) -> Attribution:
    """`implicated`: some component flipped between base and head, and evidence
    for that flip is anchored on lines the change touched."""
    if head == "SUPPORTED":
        if base == "SUPPORTED":
            return "PRE_EXISTING"
        if base == "CONTRADICTED" and implicated:
            return "CHANGE_IMPLICATED"
        return "UNATTRIBUTED"
    if head == "CONTRADICTED":
        if base == "SUPPORTED" and implicated:
            return "FIX_IMPLICATED"
        return "NOT_SUPPORTED"
    return "UNDETERMINED"


def _overlaps(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(s <= end and start <= e for s, e in spans)


def change_implicated(
    observations: list[Observation],
    statuses: dict[Side, dict[str, ComponentStatus]],
    linemap: LineMap,
) -> bool:
    for comp in statuses["head"]:
        flipped = {statuses["base"][comp], statuses["head"][comp]} == {"supported", "contradicted"}
        if not flipped:
            continue
        for o in observations:
            if o.component != comp or o.stance == "unclear":
                continue
            for a in o.citations:
                if _overlaps(linemap.changed_span(a.path, a.revision), a.start_line, a.end_line):
                    return True
    return False


def derive(
    observations: list[Observation], components: list[str], linemap: LineMap
) -> dict:
    statuses: dict[Side, dict[str, ComponentStatus]] = {
        side: {c: component_status(observations, side, c) for c in components}
        for side in ("base", "head")
    }
    rev = {side: revision_status(statuses[side]) for side in ("base", "head")}
    implicated = change_implicated(observations, statuses, linemap)
    return {
        "components": statuses,
        "revisions": rev,
        "implicated": implicated,
        "attribution": attribute(rev["base"], rev["head"], implicated),
    }
