"""§13 revision messages (PREREGISTRATION.md §13.3). Control is the P-Hybrid-2 revision
message, verbatim; treatment is control plus one sentence, the only information either arm
gets after the initial lock. Only initially incomplete pairs are forked, so the sentence is
always true when shown."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = (ROOT / "experiments" / "hop_propose" / "revision.md").read_text()
BIT = "The currently submitted evidence is not complete under the verification contract."


def message(arm: str) -> str:
    if arm == "control":
        return CONTROL
    if arm == "treatment":
        return CONTROL + "\n" + BIT + "\n"
    raise ValueError(arm)
