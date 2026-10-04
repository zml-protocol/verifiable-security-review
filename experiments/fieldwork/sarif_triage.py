"""Triage a CodeQL SARIF file: counts per rule and the highest-severity results with locations.

    uv run python experiments/fieldwork/sarif_triage.py <file.sarif> [top]

Read-only. Prints rule id, security-severity, message, and the first code location; does not
read the repository.
"""

from __future__ import annotations

import json
import sys
from collections import Counter


def severity(result: dict, rules: dict) -> float:
    rule = rules.get(result.get("ruleId", ""), {})
    props = rule.get("properties", {})
    value = props.get("security-severity")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    path = sys.argv[1]
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    doc = json.loads(open(path).read())
    runs = doc.get("runs", [])
    results = [r for run in runs for r in run.get("results", [])]
    rules = {}
    for run in runs:
        for rule in (run.get("tool", {}).get("driver", {}).get("rules") or []):
            rules[rule.get("id", "")] = rule

    counts = Counter(r.get("ruleId", "?") for r in results)
    print(f"{len(results)} results in {path}\n")
    print(f"{'count':>6}  rule")
    for rule_id, n in counts.most_common():
        sev = severity({"ruleId": rule_id}, rules)
        print(f"{n:>6}  [{sev:>4.1f}] {rule_id}")

    ranked = sorted(results, key=lambda r: severity(r, rules), reverse=True)
    print(f"\n--- top {top} by security-severity ---")
    for r in ranked[:top]:
        sev = severity(r, rules)
        loc = (r.get("locations") or [{}])[0].get("physicalLocation", {})
        artifact = loc.get("artifactLocation", {}).get("uri", "?")
        region = loc.get("region", {})
        line = region.get("startLine", "?")
        message = (r.get("message", {}) or {}).get("text", "").replace("\n", " ")[:130]
        print(f"[{sev:>4.1f}] {r.get('ruleId','?'):<45} {artifact}:{line}")
        print(f"        {message}")


if __name__ == "__main__":
    main()
