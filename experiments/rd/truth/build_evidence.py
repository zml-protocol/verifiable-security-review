"""Mechanical fact-only advisory evidence for judges (PREREGISTRATION §15.1).

The frozen charter gives adjudicators the advisory's *factual* basis, not its answer-bearing text.
This produces `advisory-evidence.md` by reading the frozen OSV snapshot advisory and dropping any
line that attributes the fix (names the guard/check, says "the fix"/"patched"/"resolved", etc.),
with an explicit inclusion/exclusion log and the source URL. It also drops the fix-commit reference
(the fix diff is supplied separately). No hand summary that could silently change meaning: content is
copied verbatim per surviving line, and every dropped line is logged.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "experiments" / "fieldwork"), str(REPO / "experiments" / "rd")]

# A line is dropped if it attributes/prescribes the remediation (answer-bearing), kept otherwise.
# Targets remediation prose ("the fix", "suggested fix", "to fix it", "defense in depth", ...) — NOT
# the factual vuln description (e.g. "renders ... without neutralizing ..."), which stays as evidence.
FIX_ATTR = re.compile(
    r"\bthe fix\b|\bfixed in\b|\bis fixed\b|\bpatch(ed|es)?\b|\bresolv(e|ed|es)\b|\bremediat|\bmitigat|"
    r"suggested fix|recommended fix|\bto fix\b|defen[cs]e in depth|closes the gap|would (also )?work|"
    r"IsSensitivePath|CheckAdminRole|CheckReadonly",
    re.I)


def build(advisory_id: str, out_path: Path) -> dict:
    import rd_precheck
    rec = rd_precheck.advisory_record({"id": advisory_id})
    if not rec:
        raise SystemExit(f"advisory {advisory_id} not found in the frozen snapshot")
    kept, dropped = [], []
    for ln in (rec.get("details") or "").split("\n"):
        (dropped if FIX_ATTR.search(ln) else kept).append(ln)

    refs = rec.get("references") or []
    kept_refs = [r for r in refs if "/commit/" not in (r.get("url") or "")]
    dropped_refs = [r for r in refs if "/commit/" in (r.get("url") or "")]
    advisory_url = next((r["url"] for r in refs if r.get("type") == "WEB" and "/security/advisories/" in r.get("url", "")),
                        refs[0]["url"] if refs else "")

    pkgs = [f"{a.get('package', {}).get('ecosystem')}: {a.get('package', {}).get('name')}"
            for a in (rec.get("affected") or [])]
    sev = "; ".join(s.get("score", "") for s in (rec.get("severity") or []))

    lines = [
        f"# Advisory factual evidence — {rec.get('id')}",
        "",
        "Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged",
        "below); no hand paraphrase. The fix diff is supplied separately, not here.",
        "",
        f"- Advisory: {rec.get('id')}  (aliases: {', '.join(rec.get('aliases') or [])})",
        f"- Affected package: {', '.join(pkgs)}",
        f"- Severity: {sev}",
        f"- Published: {rec.get('published')}",
        f"- Summary: {rec.get('summary')}",
        f"- Source: {advisory_url}",
        "",
        "## Details (verbatim, fix-attribution lines removed)",
        "",
        *kept,
        "",
        "## References (fix-commit excluded)",
        *[f"- {r.get('type')}: {r.get('url')}" for r in kept_refs],
        "",
        "## Redaction note",
        f"- {sum(1 for l in dropped if l.strip())} fix-attribution line(s) and "
        f"{len(dropped_refs)} fix-locating reference(s) were removed so this evidence carries the "
        "vulnerability facts without the remediation answer.",
        "- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), "
        "not in this judge bundle, to avoid leaking fix-attribution.",
    ]
    out_path.write_text("\n".join(lines) + "\n")
    # Author-side audit log (NOT part of the judge bundle): the verbatim excluded content.
    log = [f"# Author-side redaction log — {rec.get('id')} (NOT given to judges)", "",
           "Lines removed from the advisory details as fix-attribution:", "",
           *[f"- {l.strip()}" for l in dropped if l.strip()], "",
           "References removed as fix-locating:", "",
           *[f"- {r.get('type')}: {r.get('url')}" for r in dropped_refs]]
    out_path.with_name("advisory-redaction-log.md").write_text("\n".join(log) + "\n")
    return {"kept_lines": sum(1 for l in kept if l.strip()),
            "dropped_lines": sum(1 for l in dropped if l.strip()),
            "dropped_refs": len(dropped_refs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("advisory_id")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print(build(args.advisory_id, Path(args.out)))


if __name__ == "__main__":
    main()
