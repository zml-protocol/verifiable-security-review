# Resume Bullets

Choose the three bullets that best match the role; do not use all nine on one resume.

## AppSec version

- Built a Python/Go AppSec review harness that froze executable and independently adjudicated truth
  for 5 real vulnerability fixes using regression tests, advisory PoCs, and bounded local probes.
- Designed CodeQL-backed verification across 9 typed evidence-relation groups; none of 22 false
  conformance cases was verified, while partial providers retained explicit blind spots.
- Evaluated an LLM reviewer on fresh fixes: it attributed 3/5 correctly but produced 0/5 fully
  verified chains, exposing evidence risk that verdict-only accuracy would have hidden.

## Pentest / Offensive Security version

- Reproduced Go/Python flaws spanning information disclosure, SSRF, authorization, resource
  exhaustion, and signature verification with identical parent/fix triggers and recorded controls.
- Operationalized a `TEST → POC → PROBE` workflow that prioritizes regression tests, validates
  advisory PoCs, and time-boxes minimal local probes to avoid unbounded exploit development.
- Built blinded negative-claim checks and revision-scoped evidence controls; RD v2 observed 0/2
  false-supported revision conclusions while retaining the small denominator and uncertainty.

## General Security Engineer version

- Developed 13K+ lines of Python security automation plus Go/CodeQL fixtures and providers, backed
  by 271 tests across repository analysis, static verification, scoring, and provenance controls.
- Implemented runtime-minted citations, cross-revision rejection, append-only hash chains, artifact
  seals, budget/time guards, and score-before-review workflows for reproducible security analysis.
- Designed fail-closed controls that caught context leakage, invalid tool-input classification,
  ambiguous truth, and a contract/validator mismatch before it could become a misleading metric.
