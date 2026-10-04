# Adjudication instructions — RD requirement truth (§15.1)

You are one of two independent truth adjudicators for one security-fix fixture. Decide, for the
stated claim, which requirement items are genuinely required to establish it.

**Use only this bundle:** `definitions.yaml` (frozen operational definitions), the code context at
the `vuln` and `fixed` revisions (`code-context/`), `fix-diff.patch`, `advisory-evidence.md`, and
`execution-evidence.md`. Do not use any other source.

**Claim:** in package `ldap`, attacker-controlled input (an authentication username containing LDAP
filter metacharacters such as `*`, `(`, `)`, `\`) may lead to LDAP injection (CWE injection): the
username is interpolated into the LDAP search filter unescaped, so a metacharacter changes the
filter's meaning (e.g. `*` becomes a wildcard).
**Domain:** the attacker controls the username presented for the LDAP user lookup; every other state
may take any value the code allows.

**Task — for every item in `adjudication-sheet.yaml`:**
- Judge it **independently** against the operational definitions. Label it `REQUIRED`,
  `NOT_REQUIRED`, or `INDETERMINATE`.
- `REQUIRED` means: for the claim to hold, this exact requirement (its kind, its per-revision
  present/absent state, and its anchored program points) must be true. Do **not** label an item
  `REQUIRED` merely because the fix touches that code.
- `INDETERMINATE` means the definitions do not decide it on the evidence given.

**Missing items (optional):** if a required requirement is absent from the sheet, list it in the
frozen requirement schema (kind + per-revision anchors `{file,start_line,end_line,expression}`).

**Output — YAML, exactly this shape, nothing else:**

```yaml
labels:
  item-01: REQUIRED
  item-02: NOT_REQUIRED
  # ... one line per item id ...
missing:
  - kind: behavior
    behavior:
      vuln:  {state: absent,  context: {file: "...", start_line: 0, end_line: 0, expression: "..."}}
      fixed: {state: present, anchor:  {file: "...", start_line: 0, end_line: 0, expression: "..."}}
```

Give one label for every item id. `expression` must be the exact source line(s). No prose outside
the YAML.
