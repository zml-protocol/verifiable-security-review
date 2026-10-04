# Executable truth — GHSA-fwjx-9p69-h25h (oh-my-posh)  [author-side only]

**Not agent-facing.** §15.3 executable ground truth. This fixture is the §15.2 reserve substituted
in for flagd (go-primary #3) after flagd's behavior was ruled INDETERMINATE under BE-3.

- Fixture: `GHSA-fwjx-9p69-h25h` · repo `jandedobbeleer/oh-my-posh` · language go · CWE-150 ·
  promoted from go reserve #6.
- Revisions: **vuln = parent** `88ddbe0b0a4dd13cc345996108c9869493f2c690`;
  **fixed = fix** `edcf3c88f3fb582e84358b385c49d33d04c04224`.

## Triggering input (one rendered segment)

A prompt segment whose attacker-controlled content (a directory name, git branch/metadata, an
environment variable, or captured command output) contains terminal control characters — C0/C1
(e.g. ESC `0x1b`, BEL `0x07`, CSI, OSC) — which are rendered into the prompt via `terminal.write`.

## Security-relevant effect

The control runes reach the terminal verbatim, where they are interpreted as escape sequences
(improper neutralization of control sequences, CWE-150). Observed as the written output still
containing the raw ESC/BEL/CSI/OSC bytes.

## Base/head flip (established; same input both sides)

| | vuln (parent) | fixed |
|---|---|---|
| segment content containing ESC/BEL | the written output contains the raw control bytes | the control runes are dropped; the written output contains no raw ESC/BEL |

Effect **present at vuln, absent at fixed**, same input → executable truth established.

## Provenance (frozen selection evidence; re-recorded, not re-run by the author)

- Selection `decide`: verdict **ACCEPTED**, route **TEST** — the fix commit's regression tests
  (`src/terminal/writer_test.go`, `writer_hyperlink_test.go`) applied to both revisions (src module,
  go1.26.8, `-mod=readonly`): fix `go test ./terminal/...` exit 0 (both new cases PASS); parent exit
  1, both tests FAIL with the actual output still containing raw ESC/BEL bytes.
- Reproduction artifacts (author-side): `runs/rd/precheck/GHSA-fwjx-9p69-h25h/decision.md`,
  `test-parent.log`, `test-fix.log`.

## Scope note

Fixes only the input→effect flip. Entry/behavior anchors are authored in `requirement-truth.yaml`.
