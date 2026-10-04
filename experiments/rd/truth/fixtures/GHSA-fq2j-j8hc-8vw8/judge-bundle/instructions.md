# Adjudication instructions — RD requirement truth (§15.1)

You are one of two independent truth adjudicators for one security-fix fixture. Decide, for the
stated claim, which requirement items are genuinely required to establish it.

**Use only this bundle:** `definitions.yaml` (the frozen operational definitions), the code context
at the `vuln` and `fixed` revisions (`code-context/`), `fix-diff.patch`, `advisory-evidence.md`, and
`execution-evidence.md`. Do not use any other source.

**Claim:** attacker-controlled input may lead to CWE-200 exposure of sensitive information via
CWE-22 path handling. **Domain:** the attacker controls the HTTP request; every other state
(accounts, sessions, roles, readonly/config, environment, files, the root directory) may take any
value the code allows.

**Task — for every item in `adjudication-sheet.yaml`:**
- Judge it **independently** against the operational definitions. Label it `REQUIRED`,
  `NOT_REQUIRED`, or `INDETERMINATE`.
- `REQUIRED` means: for the claim to hold, this exact requirement (its kind, its per-revision
  present/absent state, and its anchored program points) must be true. Do **not** label an item
  `REQUIRED` merely because the fix touches that code — necessity is judged from the definitions and
  the claim, not from "the commit changed it".
- `INDETERMINATE` means the definitions do not decide it on the evidence given.

**Missing items (optional):** if you believe a required requirement is absent from the sheet, list
it in the frozen requirement schema (kind + per-revision anchors). Each anchor must resolve (a real
program point you can cite).

**Output — YAML, exactly this shape, nothing else:**

```yaml
labels:
  item-01: REQUIRED        # one line per item id in the sheet
  item-02: NOT_REQUIRED
  # ...
missing:                   # [] if none
  - kind: behavior         # entry | behavior | guard | config | dispatch_target
    behavior:              # slot field named by the item's role
      vuln:  {state: absent,  context: {file: ..., start_line: N, end_line: N, expression: "..."}}
      fixed: {state: present, anchor:  {file: ..., start_line: N, end_line: N, expression: "..."}}
```

Anchor fields are `{file, start_line, end_line, expression}` where `expression` is the exact
source line(s). Give one label for every item id. Do not add commentary outside the YAML.
