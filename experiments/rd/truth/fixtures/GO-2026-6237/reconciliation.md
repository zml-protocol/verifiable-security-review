# DHCP (GO-2026-6237) — adjudication reconciliation & truth freeze

Three-way adjudication (§15.1). Judge A = gpt-6-astra (Codex CLI, medium); Judge B =
deepseek/deepseek-flash (OpenCode `--standalone`); each fresh/isolated, tools off, one run, the
verbatim-identical bundle. Mechanical reconciliation (`agreement.check`; opaque→real via sheet-key).

## Result (three-way unanimous)

| real item | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|
| `entry-raw-frame-read` (item-06) | entry | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| `behavior-ip-payload-length-guard` (item-02) | behavior | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| 6 distractors | near-move / state-flip | NOT_REQUIRED | NOT_REQUIRED | NOT_REQUIRED | all rejected |

`indeterminate=[]`, `distractor_conflicts=[]`, `two_sided_missing=[]`, `incomplete_truth_spec=false`,
`qualifier_layer_inadmissible=false`. Both judges independently accepted the BE-3 behavior choice
(the `ipPayloadLen < udpHdrLen` guard) over the near-move distractors and the secondary buffer check.
(Judge A's paste used markdown-escaped underscores / `\[\]`; de-escaped, content unchanged.)

## Verdict — DHCP fixture truth FROZEN

- entry and behavior three-way admissible → fixture admissible (no §15.2 reserve substitution).
- Frozen scored truth: `entry = the raw-frame read upc.PacketConn.ReadFrom(pkt)` (present both
  revisions); `behavior = the added if ipPayloadLen < udpHdrLen { continue } guard` (fixed present /
  vuln absent, context = diff-aligned `if !buf.Has(udpHdrLen) {`). Secondary `buf.Has(dhcpLen)` check
  is a non-scored note.

## Process note — out-of-queue-order authoring (corrected going forward)

This fixture (queue position #4) was authored and adjudicated **before** flagd (position #3), a slip
from the frozen go-primary order (SiYuan #1, Vikunja #2, flagd #3, DHCP #4). No correctness impact:
each fixture is authored and judged independently by fresh isolated sessions seeing only their own
bundle (no cross-fixture contamination), and §15.2 reserve substitution is order-independent (all
audited primaries are admissible; no substitution triggered). Operator approved freezing DHCP as-is;
flagd (#3) is audited next.
