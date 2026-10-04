# RD §15.6 negative-control completion report

Date: 2026-10-03

## Outcome

All five frozen C.4 fixtures reached a terminal §15.6 disposition. One valid negative control was
selected:

> In Go package `github.com/insomniacslk/dhcp/dhcpv4/nclient4`, attacker-controlled input may lead
> to CWE-352 Cross-Site Request Forgery.

The author, Judge A, and Judge B each labelled that claim `NOT_SUPPORTED` in both canonical
revisions. It was the first qualifying candidate in the fixture's frozen order. The four other
fixtures contribute no usable negative control. No candidate was rewritten, relabelled, replaced,
or rerun after judge output.

| fixture | frozen candidates | disposition | downstream negative control |
|---|---|---|---|
| DHCP `GO-2026-6237` | CWE-352, CWE-22, CWE-79 | candidate 01 qualifies and is first | CWE-352 CSRF |
| SiYuan `GHSA-fq2j-j8hc-8vw8` | CWE-22, CWE-79, CWE-89 | no candidate qualifies | none |
| Vikunja `GHSA-mr3j-p26x-72x4` | CWE-918, CWE-502, CWE-601 | no candidate qualifies | none |
| LiteLLM `GHSA-hx8v-g79f-8w5f` | CWE-502, CWE-601, CWE-611 | no candidate qualifies | none |
| Mnemosyne `GHSA-xcw4-53cc-hv32` | CWE-22, CWE-79, CWE-89 | adjudication scope deviation; no usable result | none |

Thus the §15.6 negative-control corpus is **N=1**, associated with one of the five real fixtures.
The remaining four real fixture claims stay in the C corpus; they simply have no valid paired
negative-control claim.

## Three-way results

| fixture | candidate | author | Judge A | Judge B | qualifies |
|---|---|---|---|---|---|
| DHCP | 01 CWE-352 | NS / NS | NS / NS | NS / NS | yes |
| DHCP | 02 CWE-22 | NS / NS | IND / IND | NS / NS | no |
| DHCP | 03 CWE-79 | NS / NS | NS / NS | NS / NS | yes, but follows 01 |
| SiYuan | 01 CWE-22 | SUP / IND | SUP / IND | SUP / IND | no |
| SiYuan | 02 CWE-79 | IND / IND | IND / IND | IND / IND | no |
| SiYuan | 03 CWE-89 | IND / IND | IND / IND | IND / IND | no |
| Vikunja | 01 CWE-918 | IND / IND | IND / IND | IND / IND | no |
| Vikunja | 02 CWE-502 | NS / NS | IND / IND | NS / NS | no |
| Vikunja | 03 CWE-601 | NS / NS | IND / IND | NS / NS | no |
| LiteLLM | 01 CWE-502 | NS / NS | IND / IND | NS / NS | no |
| LiteLLM | 02 CWE-601 | SUP / SUP | SUP / SUP | SUP / SUP | no |
| LiteLLM | 03 CWE-611 | NS / NS | IND / IND | NS / NS | no |

Abbreviations: `NS` = `NOT_SUPPORTED`, `SUP` = `SUPPORTED`, and `IND` =
`INDETERMINATE`. Each pair is `vuln / fixed`.

Judge A consistently declined to infer package-wide absence from broad source inventories for the
Vikunja and LiteLLM candidates. Under the frozen rule that conservatism prevents qualification; it
does not authorize additional evidence, relabelling, or another judge run.

## Mnemosyne scope deviation

The frozen manifest names the package as `Mnemosyne sync server`. Its author and judge prompt,
however, asked about the broader `mnemosyne-memory` distribution and supplied 75 files from both
`mnemosyne/` and `hermes_memory_provider/`, rather than constraining evidence and the claim to
the sync-server component. That is a claim-scope mismatch against the frozen manifest.

The prompt and author labels had already been frozen and seen by both judges when this was detected,
so they remain immutable audit artifacts. The batch is not rerun or repaired. Its raw outcome was
CWE-22 and CWE-79 `SUPPORTED` in both revisions and CWE-89 `INDETERMINATE` in both revisions,
which selected no candidate even at the wider scope. Nevertheless, those labels are not treated as
a valid adjudication of the manifest-scoped claim, and the batch is excluded from downstream
negative-control selection and agreement summaries.

This deviation cannot contaminate the selected negative-control corpus because it produced no
selected item. It does reduce the number of protocol-valid completed fixture batches from five to
four.

## Downstream lock

The agent-protocol stage must use exactly the one selected negative control above:

- instantiate negative-control C runs only for DHCP / CWE-352;
- use the same neutral task shape and A → B → C flow as for a real claim;
- map canonical revisions to outward revision_A/revision_B only through the frozen seed mapping;
- compute `negative_control_false_supported_rate` over this single frozen negative-control claim's
  runs, not over all five real fixtures;
- exclude the Mnemosyne negative-control batch entirely.

The resulting negative-control metric has a very small denominator and remains only the weak
screening check described in §15.6. It must not be presented as a balanced or high-powered
evaluation of C.

## Frozen record

The candidate generator, procedure, and five candidate lists were frozen at `1019665`. Each
adjudicated directory retains the author labels and pre-judge hash, byte-identical judge prompt,
both structured judge outputs, both raw transcripts, and the mechanical reconciliation. The valid
selected item is recorded in `GO-2026-6237/result.yaml`. Chronological decisions and the scope
deviation are append-only entries in `PREREGISTRATION.md`.

This completes §15.10 step 5. The next preregistered step is the agent protocol and synthetic
plumbing pilot, followed by protocol freeze before any measured agent run.

