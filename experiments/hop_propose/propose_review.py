"""Blind review of novel hops (PREREGISTRATION.md §11.5).

    uv run python experiments/hop_propose/propose_review.py export

A novel hop is a locked hop (initial or final, either arm) that does not match a golden hop.
Occurrences naming the same nodes form one review unit. `export` writes, under
runs/hop_propose/<protocol>/review/:

- sheet.md         what reviewers see: per unit, in seeded random order, the revision, the
                   relation's definition, both endpoints and their code in that revision.
                   Never the arm, phase, verdict, golden match or the agent's text.
- units.json       private map from review id to unit and occurrences (not for reviewers).
- labels.template.yaml   one entry per review id: TRUE, FALSE or INDETERMINATE.

Filled label files are committed as results/p-hybrid-2-review-{primary,secondary}.yaml.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import propose_run as R
import propose_score as S

SEED = 20260930
CONTEXT = 6
FORBIDDEN = ("control", "treatment", "VERIFIED", "UNVERIFIED", "golden", "initial", "final")


def occurrences(pilot: bool) -> dict[str, list[dict]]:
    """Unit key -> every occurrence (block, phase, hop id) with its canonical hop."""
    result = S.score(pilot)
    units: dict[str, list[dict]] = {}
    root = R.runs_root(pilot)
    for pair in result["pairs"]:
        block = root / pair["fixture"] / f"r{pair['repeat']}"
        for phase in ("initial", *R.ARMS):
            state = S.state_of(block / phase)
            locked = {h["id"]: h for h in (state["initial"] if phase == "initial" else state["final"]) or []}
            for row in pair[phase]["hops"]:
                if row["unit"] is not None:
                    units.setdefault(row["unit"], []).append(
                        {"block": pair["block"], "phase": phase, "hop": locked[row["id"]]})
    return units


def code_context(text_of, revision: str, ep: dict) -> str:
    text = text_of(revision, ep["file"])
    lines = text.splitlines() if text else []
    lo, hi = max(1, ep["start_line"] - CONTEXT), min(len(lines), ep["end_line"] + CONTEXT)
    out = []
    for n in range(lo, hi + 1):
        mark = ">>" if ep["start_line"] <= n <= ep["end_line"] else "  "
        out.append(f"{mark}{n:>6} | {lines[n - 1]}")
    return "\n".join(out)


def export(args: argparse.Namespace) -> None:
    units = occurrences(args.pilot)
    keys = sorted(units)
    random.Random(SEED).shuffle(keys)
    out_dir = R.runs_root(args.pilot) / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    readers = {}
    instructions = ("For each item decide whether the stated link holds in the code shown, "
                    "under the relation's definition: TRUE, FALSE, or INDETERMINATE (the code "
                    "shown and the repository do not settle it). Judge each item on its own.")
    sheet = ["# Hop review sheet", "", instructions, ""]
    private, template, generated = {}, {}, list(sheet)
    for i, unit in enumerate(keys, 1):
        rid = f"R{i:03d}"
        key = json.loads(unit)
        fixture, revision, relation = key[0], key[1], key[2]
        hop = units[unit][0]["hop"]
        if fixture not in readers:
            _, case = R.case_of(fixture, args.pilot)
            # the repository's own name, never the case id (which names the vulnerability)
            readers[fixture] = (R.text_reader(case), Path(case.repo.path).name.removesuffix(".git"))
        definition = R.VOCABULARY["relations"][relation].strip()
        kinds = R.RELATIONS.get(relation, {})
        text_of, repo_name = readers[fixture]
        head = [f"## {rid}", "", f"- code: {repo_name}, revision `{revision}`",
                f"- relation `{relation}`: {definition}"]
        sheet += head
        generated += head
        for side in ("from", "to"):
            ep = hop[side]
            kind = ", ".join(kinds[side]["kinds"]) if kinds else "any"
            line = (f"- **{side}** ({kind}): `{ep['file']}` lines {ep['start_line']}-"
                    f"{ep['end_line']}, starting at `{ep['expression']}`")
            generated.append(line)
            sheet += [line, "", "```", code_context(text_of, revision, ep), "```", ""]
        private[rid] = {"key": unit, "occurrences": [
            {"block": o["block"], "phase": o["phase"], "hop_id": o["hop"]["id"]} for o in units[unit]]}
        template[rid] = None
    text = "\n".join(sheet) + "\n"
    # only the text this tool writes is checked; code and expressions are the repository's
    leaked = [w for w in FORBIDDEN
              if any(re.search(rf"\b{w}\b", g.split(", starting at")[0]) for g in generated)]
    if leaked:
        sys.exit(f"sheet would show {leaked}; refusing to write it")
    (out_dir / "sheet.md").write_text(text)
    (out_dir / "units.json").write_text(json.dumps(private, indent=1))
    (out_dir / "labels.template.yaml").write_text(
        "# Label each item TRUE | FALSE | INDETERMINATE. The scorer requires the reviewer block;\n"
        "# independent: not involved in this project, never saw its golden, verifiers or protocol.\n"
        "reviewer:\n  type:   # human | model\n  name:\n  date:\n"
        "  attestation:\n    independent:   # true\n    saw_arms:   # false\n"
        "    saw_verdicts:   # false\nlabels:\n"
        + "".join(f"  {rid}: {{label: , note: }}\n" for rid in template))
    print(f"{len(keys)} review units -> {out_dir.relative_to(R.ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--pilot", action="store_true")
    args = ap.parse_args()
    {"export": export}[args.cmd](args)


if __name__ == "__main__":
    main()
