# Execution evidence (observed facts) — GHSA-fwjx-9p69-h25h

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input: a rendered prompt segment whose content contains terminal control bytes — e.g. a git commit
  subject (or directory name) embedding `ESC` (`0x1b`) / `BEL` (`0x07`) as part of an OSC sequence.
- Method: the fix commit's regression tests (`src/terminal/writer_test.go`,
  `writer_hyperlink_test.go`) applied to both revisions (src module, go1.26.8, `-mod=readonly`),
  `go test ./terminal/...`.

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| segment content containing ESC/BEL | test fails: the written output still contains the raw ESC/BEL control bytes | test passes: the written output contains no raw ESC/BEL control bytes |

Same input, the raw control bytes appear in the output on the vuln revision and not on the fixed
revision.
