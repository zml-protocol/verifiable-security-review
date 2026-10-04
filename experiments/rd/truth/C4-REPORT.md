# RD §15 C.4 fixture-truth completion report

Date: 2026-10-03

## Outcome

The preregistered target was **N=8**: four Go and four Python fixtures, with two same-language
reserves per tranche. Frozen three-way-admissible truth was realized for **N=5**:

| language | planned | realized | frozen fixtures |
|---|---:|---:|---|
| Go | 4 | 3 | SiYuan `GHSA-fq2j-j8hc-8vw8`; Vikunja `GHSA-mr3j-p26x-72x4`; DHCP `GO-2026-6237` |
| Python | 4 | 2 | LiteLLM `GHSA-hx8v-g79f-8w5f`; Mnemosyne `GHSA-xcw4-53cc-hv32` |
| **total** | **8** | **5** | — |

For each frozen fixture, both real core items (entry and behavior) were labeled `REQUIRED` by the
author and both independent judges, all six generated near-move/state-flip distractors were labeled
`NOT_REQUIRED` by both judges, and neither judge proposed a missing requirement. Across the five
frozen fixtures this is 10 unanimous core items and 30 unanimously rejected distractors.

## Attrition record

| fixture | role at truth time | disposition | reason | judge exposure |
|---|---|---|---|---|
| flagd `GHSA-rmrf-g9r3-73pm` | Go primary | inadmissible | BE-3: two independent service-setup branches each decide the body-limit effect and cannot be ordered | none |
| oh-my-posh `GHSA-fwjx-9p69-h25h` | Go reserve 1 | inadmissible | entry three-way disagreement; author used a coarse function anchor instead of the exact parameter | two judges |
| fabric-ca `GHSA-xghw-p77p-3r7x` | Go reserve 2 | inadmissible | behavior disagreement; author used a sub-expression rather than AC-2's first reading statement | two judges |
| Reflex `PYSEC-2026-1868` | Python primary 2 | inadmissible | JavaScript entry/behavior inside one Python f-string collapse to the same `Constant` identity | none |
| llama-stack `GHSA-xmfj-7pp5-fxr6` | Python primary 3 | inadmissible | CWE-532 secret is non-attacker-controlled state under the frozen claim model; natural parameters also resolve only to containing functions | none |
| Flask-Reuploaded `GHSA-937x-gpqr-72gg` | Python reserve 2 | inadmissible | EN-1 `name` parameter resolves to the containing `FunctionDef`; later assignments are EN-3-derived | none |
| AGiXT `GHSA-5gfj-64gh-mgmw` | Python primary 4 | inadmissible | request/command/path parameters and the advisory's inline keyword source resolve to containing function/call nodes, not exact entry definitions | none |

Mnemosyne, Python reserve 1, successfully substituted for Reflex. Flask-Reuploaded could not
substitute for llama-stack. With the reserve lists exhausted, the two tranches were reduced rather
than backfilled, exactly as preregistered.

## Interpretation

- The gate worked as designed: no matcher/definition change was made to rescue a selected fixture,
  no author truth was rewritten after judge exposure, and no extra reserve or quota-skipped candidate
  was introduced.
- Two Go reserve losses are author anchor-granularity errors, not inherent fixture or provider
  failures. They remain in the attrition denominator and audit record.
- Four Python losses were caught before judge exposure by the mandatory self-review. They measure a
  real boundary of the frozen source-node representation: embedded-language statements and several
  Python parameter/binding layouts cannot be represented at the required exact granularity.
- llama-stack additionally exposes a claim-domain boundary: secret disclosure does not naturally
  provide the attacker-controlled triggering input required by the frozen entry definition.
- The realized corpus is small and selected through a stringent truth gate. Downstream results must
  be reported descriptively; the reduction from N=8 to N=5 and every exclusion above must remain
  visible.

## Frozen record

Each admissible fixture directory contains executable truth, author requirement truth, mandatory
anchor self-review, pre-judge hashes, opaque adjudication sheet/key, the byte-frozen judge bundle and
prompt, raw and structured outputs from both judges, and mechanical reconciliation. Each
inadmissible fixture directory records the exact pre-judge or post-judge failure and §15.2
disposition. `PREREGISTRATION.md` contains the chronological change-log entries.

This completes §15.10 step 4. The next preregistered step is §15.6 negative-control generation,
three-way adjudication, and freezing for these five admissible fixtures.
