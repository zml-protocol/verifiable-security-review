"""The one-shot verifier feedback of the treatment arm (PREREGISTRATION.md §11.2).

Whitelist: hop id, state and a fixed legend. Never a resolution target, a candidate, a
next hop, golden information or verifier internals. The treatment revision message is the
control message plus this block, byte for byte.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROL = (HERE / "revision.md").read_text()

HEADER = "An automated verifier checked each of your initial hops:"
LEGEND = {
    "VERIFIED": "the verifier confirmed the relation between the hop's two endpoints.",
    "UNVERIFIED": "the verifier cannot confirm this hop; it may still be true.",
}


def block(verdicts: list[tuple[str, str]]) -> str:
    """verdicts: (hop id, state) in hop order."""
    for _, state in verdicts:
        if state not in LEGEND:
            raise ValueError(f"no whitelisted feedback for state {state!r}")
    rows = [f"{hid}  {state}" for hid, state in verdicts] or ["(no initial hops were locked)"]
    legend = [f"{state}: {text}" for state, text in LEGEND.items()]
    return "\n".join([HEADER, *rows, "", *legend]) + "\n"


def message(arm: str, verdicts: list[tuple[str, str]]) -> str:
    if arm == "control":
        return CONTROL
    if arm == "treatment":
        return CONTROL + "\n" + block(verdicts)
    raise ValueError(arm)
