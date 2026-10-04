# Reflex (PYSEC-2026-1868) — INADMISSIBLE (entry/behavior INDETERMINATE_TRUTH); reserve substituted

Python primary queue position #2. **Not frozen as an admissible fixture truth.** The executable
open-redirect flip is established, but the exact requirement entry and behavior cannot be expressed
by the frozen Python anchor matcher. Under the frozen harness rule this is a measurement result, not
a reason to change the matcher or resolver.

## Executable truth remains established

The identical Node DOM-shim probe executed the generated `redirect_script()` at both revisions:

- vuln: `redirect_to=http://evil.example/landing` triggers automatic navigation to that URL;
- fixed: the same input does not navigate and emits `Reflex: Not redirecting to different hostname`;
- fixed still navigates to a legitimate same-Codespace different-port URL.

This input/result flip is real. The inadmissibility concerns only the §15.3 requirement anchors.

## Why the requirement truth is not expressible

The attacker input extraction and all security-relevant operations are JavaScript text embedded in
the Python function's returned multiline f-string (`reflex/utils/codespaces.py`):

- entry candidate: `params.get("redirect_to")`;
- vulnerable behavior/sink candidates: `a.href = ...` and `a.click()`;
- fixed changed-check candidates: `sameHostnameDifferentPort(...)` and
  `redirect_to.hostname.endsWith(".app.github.dev")`;
- fixed assignment/sink candidates: `a.href = redirect_to.href` and `a.click()`.

The frozen matcher for a Python fixture is CPython `ast`. The strict resolver can locate each source
line, but every line inside the generated JavaScript string resolves to the **same Python `Constant`
node** in its revision:

| candidate lines | revision | node type | structural path | content digest |
|---|---|---|---|---|
| params construction, `params.get`, `a.click()` | vuln | `Constant` | `(11, 4, 0, 0)` | `c2f6cfc...` |
| extraction, both guards, assignment, `a.click()` | fixed | `Constant` | `(11, 4, 0, 0)` | `eda6c0ad...` |

Consequences:

1. An anchor cannot identify the exact JavaScript statement named by EN-2 or BE-1/BE-3; it identifies
   the entire generated-script literal.
2. Entry, behavior, sink, and near-move distractors collapse to one node identity within a revision.
3. Using the whole `Constant` merely because it contains the desired JavaScript violates the
   mandatory anchor self-review's exact statement/parameter rule.

There is therefore no valid statement-granular entry or behavior item to put into
`requirement-truth.yaml`. At least one core item is `INDETERMINATE_TRUTH`, so the fixture is
inadmissible without exposing a bundle to judges. No tooling change is permitted.

## Disposition (§15.2 substitution)

- The frozen selection queue and append-only selection log remain unchanged.
- First Python reserve promoted: **Mnemosyne (`GHSA-xcw4-53cc-hv32`, cryptography, reserve position
  #21)**. The per-CWE-class quota remains satisfied: the current Python set has SSRF (LiteLLM),
  cryptography (Mnemosyne), information exposure (llama-stack), and path traversal (AGiXT).
- No judges were run for Reflex because no exact core anchors can be authored under the frozen
  matcher. The next work item is Mnemosyne, before returning to the remaining Python primaries.
