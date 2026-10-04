"""Write the adjudicators' labeling sheet for the RD decidability test (PREREGISTRATION.md §15.1).

    uv run python experiments/rd/boundary/sheet.py --round 1

Writes, under results/:
- rd-boundary-r<N>-sheet.md            what each adjudicator gets: the frozen definitions verbatim
                                       (without the file's leading comment block),
                                       the numbered source, and the cases with opaque ids. Never the
                                       author's labels, rule ids, tiers or descriptive names.
- rd-boundary-r<N>-labels.template.yaml the output format.
- rd-boundary-r<N>-instructions.md     for the operator: who may label, and the session prompt.
- rd-boundary-r<N>-manifest.json       the hashes of the definitions, case files and sheet, and the
                                       case ids; decide.py refuses label files that do not match it.

Both adjudicators get the identical sheet.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "results"
DEFS = ROOT / "experiments" / "rd" / "definitions.yaml"
sys.path.insert(0, str(HERE))

import check as C

LANG = {"go": "go", "python": "python"}
RELATION_LABELS = ("TRUE", "FALSE", "INDETERMINATE")
REQUIREMENT_LABELS = ("REQUIRED", "NOT_REQUIRED", "INDETERMINATE")
ATTESTATION = {"independent": True, "saw_author_labels": False, "saw_project_history": False}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbered(text: str) -> str:
    return "".join(f"{i:4} | {line}" for i, line in enumerate(text.splitlines(True), 1))


def at(anchor: dict) -> str:
    return f"`{anchor['expression']}`@{anchor['start_line']}"


def realization(real: dict) -> str:
    if real["state"] == "present":
        return f"present {at(real['anchor'])}"
    return f"absent (context {at(real['context'])})"


def semantic(item: dict) -> str:
    sem = item.get("semantic") or {}
    if "expected" in sem:
        return f"expected: {sem['expected']}"
    if "expected_condition" in sem:
        cond = sem["expected_condition"]
        value = f", value: {json.dumps(cond['value'])}" if "value" in cond else ""
        return f"expected_condition: {{op: {cond['op']}{value}}}"
    return ""


def definitions_text() -> str:
    """The frozen definitions without the file's leading comment block, which names project files
    and describes the author's side; every definition entry is shown verbatim."""
    lines = DEFS.read_text().splitlines(True)
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "".join(lines)


def subset(rel: dict, req: dict, groups: set[str] | None) -> tuple[dict, dict]:
    """A round limited to some groups (§15.1: a revised group is relabelled in full): the relation
    cases and requirement items of those groups only."""
    if groups is None:
        return rel, req
    import decide
    group_of = decide.groups(rel, req)
    rel = {**rel, "hops": [h for h in rel["hops"] if group_of[h["id"]] in groups]}
    items = [it for it in req["items"] if group_of[it["id"]] in groups]
    keep = {it["scenario"] for it in items}
    req = {**req, "items": items, "scenarios": {k: v for k, v in req["scenarios"].items() if k in keep}}
    return rel, req


def sheet(rel: dict, req: dict) -> str:
    out = [
        "# Definition check: labeling sheet\n\n",
        (f"Label {len(rel['hops'])} relation cases (Part 1) and {len(req['items'])} requirement items "
         "(Part 2) against the definitions below. " if rel["hops"] else
         f"Label {len(req['items'])} requirement items (Part 2) against the definitions below. ")
        + ("Use only this sheet: the definitions, the code shown and general knowledge of Go and "
           "Python. Judge each case on its own.\n\n"),
        "## How to label\n\n",
        ("- An anchor written `expr`@N is the program point where the expression `expr` starts on line N "
         "of the file shown.\n"),
        ("" if not rel["hops"] else "- **Part 1, relation cases**: `\"TRUE\"` if the named relation holds from `from` to `to` under the "
         "definitions; `\"FALSE\"` if it does not; `\"INDETERMINATE\"` if the definitions do not settle it.\n"),
        ("- **Part 2, requirement items**: each scenario states a claim and shows two revisions. With a "
         "triggering input, the claimed effect occurs at `vuln` and does not occur at `fixed`. Each item "
         "proposes one requirement (an entry, a behavior, or a qualifier with its kind) with its "
         "realization at each revision (present with an anchor, or absent with a context). Label "
         "`\"REQUIRED\"` if this exact item, with every field, is a correct requirement under the "
         "definitions; `\"NOT_REQUIRED\"` if it is not (a wrong role, kind, field, state, anchor or "
         "context makes it NOT_REQUIRED); `\"INDETERMINATE\"` if the definitions do not settle it. "
         "Items of one scenario may be alternatives to each other; any number of them may be wrong.\n"),
        "- A short note is welcome but optional.\n\n",
        "## Definitions (verbatim)\n\n```yaml\n" + definitions_text() + "```\n\n",
    ]
    if rel["hops"]:
        out.append("## Part 1. Relation cases\n\n")
    for fid, fixture in rel["fixtures"].items():
        files = sorted({h[side]["file"] for h in rel["hops"] if h["fixture"] == fid for side in ("from", "to")})
        for f in files:
            text = C.bridge.verify.source(fixture, "base", f)
            out.append(f"### {f} ({fixture['language']})\n\n```{LANG[fixture['language']]}\n{numbered(text)}```\n\n")
    if rel["hops"]:
        out.append("| id | file | relation | from | to |\n|---|---|---|---|---|\n")
    for h in rel["hops"]:
        out.append(f"| {h['id']} | {h['from']['file']} | {h['relation']} | {at(h['from'])} | {at(h['to'])} |\n")
    out.append("\n## Part 2. Requirement scenarios\n\n")
    for sid, sc in req["scenarios"].items():
        fixture = req["fixtures"][sc["repo_fixture"]]
        lang = LANG[fixture["language"]]
        f = sc["file"]
        vuln = C.bridge.verify.source(fixture, "vuln", f)
        fixed = C.bridge.verify.source(fixture, "fixed", f)
        diff = "".join(difflib.unified_diff(vuln.splitlines(True), fixed.splitlines(True),
                                            f"vuln/{f}", f"fixed/{f}"))
        out.append(f"### Scenario {sid} ({f})\n\n**Claim:** {sc['claim']}\n\n"
                   f"**What the attacker controls; other state:** {sc['domain']}\n\n"
                   f"#### vuln\n\n```{lang}\n{numbered(vuln)}```\n\n"
                   f"#### fixed\n\n```{lang}\n{numbered(fixed)}```\n\n"
                   f"#### diff\n\n```diff\n{diff}```\n\n")
        out.append("| id | role | kind | semantic | realization per revision |\n|---|---|---|---|---|\n")
        for it in req["items"]:
            if it["scenario"] != sid:
                continue
            slots = "<br>".join(
                f"{name}: vuln {realization(slot['vuln'])}; fixed {realization(slot['fixed'])}"
                for name, slot in it["slots"].items())
            out.append(f"| {it['id']} | {it['role']} | {it.get('kind', '')} | {semantic(it)} | {slots} |\n")
        out.append("\n")
    where = ("every id in Part 1 under `relations`, every id in Part 2 under `requirements`"
             if rel["hops"] else "`relations` left empty, every id in Part 2 under `requirements`")
    out.append("## Output\n\nReply with YAML in exactly the form of the template "
               f"(`rd-boundary-labels.template.yaml`): {where}. Write every label and the date as a "
               "quoted string.\n")
    return "".join(out)


def template(rel: dict, req: dict) -> str:
    lines = ["# Label every case. Labels are quoted strings: relations \"TRUE\" | \"FALSE\" | \"INDETERMINATE\";",
             "# requirements \"REQUIRED\" | \"NOT_REQUIRED\" | \"INDETERMINATE\".",
             "reviewer:",
             "  type: \"\"        # \"model\" (or \"human\")",
             "  name: \"\"        # e.g. \"<model name>, new conversation\"",
             "  date: \"\"        # \"YYYY-MM-DD\"",
             "  attestation:",
             "    independent: true          # never saw this project's history, labels or expected answers",
             "    saw_author_labels: false",
             "    saw_project_history: false",
             "relations:"]
    lines += [f"  {h['id']}: {{label: \"\", note: \"\"}}" for h in rel["hops"]]
    if not rel["hops"]:
        lines[-1] = "relations: {}"
    lines.append("requirements:")
    lines += [f"  {it['id']}: {{label: \"\", note: \"\"}}" for it in req["items"]]
    return "\n".join(lines) + "\n"


def instructions(n: int, sheet_name: str, template_name: str, relations: bool = True) -> str:
    part1 = ('Part 1: for each relation case, "TRUE", "FALSE" or "INDETERMINATE" (the definitions do\n'
             '> not settle it). ') if relations else ""
    return f"""# RD definition check, round {n}: instructions for the operator (PREREGISTRATION.md §15.1)

Two adjudicators label the same sheet independently. Give each ONLY `{sheet_name}` and
`{template_name}`. Nothing else from the project.

## Who may label

- Two **brand-new** model conversations, neither of them Claude (the agent under test is Claude).
  Best: two different non-Claude model families. If only ChatGPT is available, use two separate
  Temporary Chats (or memory off); the report then says they are not independent model families.
- Neither may see the other's answers, the author's labels, this project's history, or any earlier
  conversation about it. Run them in any order.
- A conversation that has seen this project (including the one relaying this) may not label.

## Steps

1. Open a new conversation (Temporary Chat / memory off), attach both files, paste the prompt below.
2. Check the reply has a label for every id (relations r.., requirements q..) and a filled reviewer
   block. If the YAML does not parse, you may ask the same conversation once to fix the format only.
3. Save the reply verbatim as `results/rd-boundary-r{n}-judge-a.yaml` (first adjudicator) or
   `results/rd-boundary-r{n}-judge-b.yaml` (second). Do not edit labels or notes.

## Prompt

> You will label cases for a definition check. The attached sheet gives a set of definitions, some
> source code, and cases with ids. Label every case strictly against the definitions in the sheet,
> using only the sheet and general knowledge of Go and Python. {part1}Part 2: for each
> requirement item, "REQUIRED", "NOT_REQUIRED" or "INDETERMINATE". Judge each case on its own.
> Reply with YAML exactly in the form of the attached template: fill the reviewer block (type
> "model", your model name followed by ", new conversation", today's date as "YYYY-MM-DD", and
> the attestation as given), then a label and an optional short note for every id. Write every
> label and the date as quoted strings.
"""


def write(n: int, groups: set[str] | None = None) -> dict:
    rel, req = C.load("relation_cases.yaml"), C.load("requirement_cases.yaml")
    if C.leaks(rel, req):
        sys.exit("label fields in the case files")
    rel, req = subset(rel, req, groups)
    names = {k: f"rd-boundary-r{n}-{k}" for k in ("sheet", "template", "instructions", "manifest")}
    paths = {"sheet": RESULTS / f"{names['sheet']}.md",
             "template": RESULTS / f"rd-boundary-r{n}-labels.template.yaml",
             "instructions": RESULTS / f"{names['instructions']}.md",
             "manifest": RESULTS / f"{names['manifest']}.json"}
    paths["sheet"].write_text(sheet(rel, req))
    paths["template"].write_text(template(rel, req))
    paths["instructions"].write_text(instructions(n, paths["sheet"].name, paths["template"].name,
                                                  relations=bool(rel["hops"])))
    manifest = {
        "round": n,
        "groups": sorted(groups) if groups else "all",
        "definitions": {"file": str(DEFS.relative_to(ROOT)), "sha256": sha256(DEFS)},
        "cases": {name: sha256(HERE / name) for name in ("relation_cases.yaml", "requirement_cases.yaml")},
        "sheet_sha256": sha256(paths["sheet"]),
        "relations": [h["id"] for h in rel["hops"]],
        "requirements": [it["id"] for it in req["items"]],
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--groups", help="comma-separated groups to relabel (default: all)")
    a = ap.parse_args()
    m = write(a.round, set(a.groups.split(",")) if a.groups else None)
    print(f"round {m['round']}: {len(m['relations'])} relation cases, {len(m['requirements'])} requirement "
          f"items, sheet {m['sheet_sha256'][:12]}")


if __name__ == "__main__":
    main()
