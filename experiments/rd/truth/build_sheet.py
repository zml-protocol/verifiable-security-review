"""Build the vuln/fixed opaque adjudication sheet + judge evidence bundle for one fixture (§15.1).

Orchestration only — no identity/scoring semantics. The TRUTH-CONSTRUCTION / ADJUDICATION layer uses
canonical `vuln`/`fixed` revision labels (the two fresh judges are truth adjudicators and, per the
frozen §15.1 charter, see the fix diff + executable facts, so before/after is not hidden from them).
The agent-facing seed map (revision_map) is a separate, later concern and is NOT used here.

The frozen `distractors.py`/`anchor_machinery.py` require `revision_A`/`revision_B` slot keys, so this
module maps `vuln->revision_A`, `fixed->revision_B` *positionally* (fixed, no seed) only to drive those
tools, then relabels back to `vuln`/`fixed` on output. `freeze.verify_freeze()` gates the build.

Emits under the fixture dir:
- `adjudication-sheet.yaml`  — opaque, randomized, NO author labels, slots in vuln/fixed.
- `sheet-key.yaml`           — author-side: opaque id -> real id / author_expected / distractor rule.
- `code-context/vuln.md`, `code-context/fixed.md` — the relevant source at each revision.
"""

from __future__ import annotations

import argparse
import copy
import random
from pathlib import Path

import yaml

import anchor_machinery
import distractors
import freeze
import resolver
import vocabulary

ROLE_DIR = {"vuln": "parent", "fixed": "fix"}
CANON = ("vuln", "fixed")
POS = {"vuln": "revision_A", "fixed": "revision_B"}      # canonical -> positional (tool-facing)
INV = {"revision_A": "vuln", "revision_B": "fixed"}      # positional -> canonical (output)
AUTHOR_FIELDS = ("author_expected", "rationale", "note", "distractor")


def _relabel(item: dict, mapping: dict) -> dict:
    """Relabel the revision keys of every slot field of an item."""
    out = copy.deepcopy(item)
    for key, value in list(out.items()):
        if isinstance(value, dict) and (set(value) & (set(CANON) | set(INV))):
            out[key] = {mapping.get(rev, rev): rv for rev, rv in value.items()}
    return out


def _slots(item: dict, keys):
    for key, value in item.items():
        if isinstance(value, dict) and set(value) & set(keys):
            yield key, value


def _source_provider(trees_dir: Path):
    def provider(pos_rev: str, file: str) -> str:
        role = INV[pos_rev]  # revision_A->vuln(parent), revision_B->fixed(fix)
        p = trees_dir / ROLE_DIR[role] / file
        if not p.exists():
            raise FileNotFoundError(f"source not found for {role!r}: {p}")
        return p.read_text()
    return provider


def _validate_resolves(item: dict, language: str, source_provider) -> None:
    for _, slot in _slots(item, INV.keys()):
        for rev in ("revision_A", "revision_B"):
            r = slot.get(rev) or {}
            key = "anchor" if r.get("state") == "present" else ("context" if r.get("state") == "absent" else None)
            if key is None or r.get(key) is None:
                continue
            resolver.resolve_identity(r[key], language=language, revision=rev,
                                      source=source_provider(rev, r[key]["file"]))


def _strip(item: dict, opaque_id: str) -> dict:
    out = {k: v for k, v in copy.deepcopy(item).items() if k not in AUTHOR_FIELDS and k != "id"}
    return {"id": opaque_id, **out}


def _write_code_context(outward_items: list, language: str, source_provider, out_dir: Path) -> None:
    anchors = [r[k] for it in outward_items for _, slot in _slots(it, INV.keys())
               for rev in ("revision_A", "revision_B") for r in [slot.get(rev) or {}]
               for k in [("anchor" if r.get("state") == "present" else "context")]
               if isinstance(r.get(k), dict)]
    files = sorted({a["file"] for a in anchors})
    ctx_dir = out_dir / "code-context"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    for pos_rev, canon in INV.items():
        lines_md = [f"# Code context — {canon} revision\n"]
        for file in files:
            fa = [a for a in anchors if a["file"] == file]
            lo = max(1, min(a["start_line"] for a in fa) - 20)
            hi = max(a["end_line"] for a in fa) + 25
            src = source_provider(pos_rev, file).split("\n")
            hi = min(hi, len(src))
            lines_md.append(f"\n## {file} (lines {lo}-{hi})\n\n```{language}")
            lines_md += [f"{n:4d}  {src[n - 1]}" for n in range(lo, hi + 1)]
            lines_md.append("```")
        (ctx_dir / f"{canon}.md").write_text("\n".join(lines_md) + "\n")


def build(fixture_id: str, truth_path: Path, trees_dir: Path, out_dir: Path) -> dict:
    freeze.verify_freeze()  # refuse if any frozen tool/provenance drifted
    truth = yaml.safe_load(truth_path.read_text())
    language = truth["truth_meta"]["language"]
    scored = list(truth.get("items", []))                       # canonical vuln/fixed items
    internal = [_relabel(it, POS) for it in scored]             # -> positional A/B for frozen tools

    source_provider = _source_provider(trees_dir)
    relocate = anchor_machinery.make_relocator(language, source_provider)
    allowed = tuple(vocabulary.allowed_qualifier_kinds())

    tagged, ledgers = [], []
    for item in internal:
        _validate_resolves(item, language, source_provider)
        tagged.append(("real", item))
        dists, ledger = distractors.generate_with_ledger(
            item, relocator=relocate, context_for=anchor_machinery.context_for,
            present_for=anchor_machinery.present_for, rebuild=anchor_machinery.rebuild, kinds=allowed)
        ledgers.extend(ledger)
        for d in dists:
            _validate_resolves(d, language, source_provider)
            tagged.append(("distractor", d))

    random.Random(f"sheet:{fixture_id}").shuffle(tagged)

    sheet_items, key = [], []
    for n, (tag, it) in enumerate(tagged, 1):
        opaque = f"item-{n:02d}"
        sheet_items.append(_relabel(_strip(it, opaque), INV))   # back to vuln/fixed for the sheet
        key.append({"opaque_id": opaque, "real_id": it.get("id"), "is_distractor": tag == "distractor",
                    "author_expected": it.get("author_expected", "REQUIRED")})

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = {
        "fixture": fixture_id,
        "revisions": list(CANON),
        "instructions": ("Label each item REQUIRED / NOT_REQUIRED / INDETERMINATE against the frozen "
                         "definitions and the code context. You may add a missing required item in the "
                         "frozen requirement schema (kind + per-revision anchors)."),
        "items": sheet_items,
    }
    (out_dir / "adjudication-sheet.yaml").write_text(yaml.safe_dump(sheet, sort_keys=False, allow_unicode=True))
    (out_dir / "sheet-key.yaml").write_text(yaml.safe_dump(
        {"fixture": fixture_id, "revision_labels": "canonical vuln/fixed (no seed map at this layer)",
         "key": key, "distractor_ledger": ledgers}, sort_keys=False, allow_unicode=True))
    _write_code_context([_relabel(it, POS) for it in scored], language, source_provider, out_dir)
    return {"items": len(sheet_items), "real": sum(1 for k in key if not k["is_distractor"]),
            "distractors": sum(1 for k in key if k["is_distractor"])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fixture_id")
    ap.add_argument("--truth", required=True)
    ap.add_argument("--trees", required=True, help="dir with parent/ and fix/ checkouts")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print(build(args.fixture_id, Path(args.truth), Path(args.trees), Path(args.out)))


if __name__ == "__main__":
    main()
