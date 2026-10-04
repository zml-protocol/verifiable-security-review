# oh-my-posh (GHSA-fwjx-9p69-h25h) — adjudication reconciliation: INADMISSIBLE (entry INDETERMINATE)

Three-way adjudication (§15.1). Judge A = gpt-6-astra (Codex CLI, medium); Judge B =
deepseek/deepseek-flash (OpenCode `--standalone`); each fresh/isolated, tools off, one run, the
verbatim-identical bundle. Mechanical reconciliation (`agreement.check`; opaque→real via sheet-key).

## Result (not three-way unanimous)

| real item | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|
| `behavior-drop-control-rune` (item-02) | behavior | REQUIRED | REQUIRED | REQUIRED | admissible |
| `entry-write-rune` (item-07) | entry | REQUIRED | **INDETERMINATE** | REQUIRED | **INDETERMINATE** |

6 distractors all NOT_REQUIRED by both judges; no distractor conflicts. (Judge A's paste used
markdown-escaped underscores; de-escaped, content unchanged.)

## Verdict — INADMISSIBLE; §15.2 substitution

Per §15.1, a fixture whose **entry or behavior** is `INDETERMINATE_TRUTH` is inadmissible, even when
the other is admissible. Here the behavior is three-way admissible but the **entry is indeterminate**
(author + Judge B REQUIRED; Judge A INDETERMINATE). The entry anchor (`func write(s rune)`, EN-1 — the
parameter holding the attacker rune) was author-flagged as a coarse/debatable anchor for an internal
per-rune function; Judge A did not confirm it. Anchor sets are frozen before adjudication (one anchor
was provided) and there is no author re-anchor step after a label three-way disagreement, so the
fixture is inadmissible and replaced from the Go reserve queue.

- Next Go reserve promoted: **fabric-ca (`GHSA-xghw-p77p-3r7x`, injection, reserve #7)**. CWE-class
  quota re-checked (per_cwe_class ≤ 2 holds): new go-primary set = SiYuan, Vikunja, DHCP, fabric-ca.
  **This consumes the last Go reserve**; if fabric-ca is also inadmissible, §15.2 requires reducing N
  (conditions are not relaxed).
- Operator-approved. Judge outputs (`judge-a.yaml`, `judge-b.yaml`) are the record.

This is the second Go substitution (flagd: behavior INDETERMINATE under BE-3; oh-my-posh: entry
INDETERMINATE by three-way disagreement). The executable-truth flips for both remain real; the
inadmissibility concerns only the §15.3 requirement truth.
