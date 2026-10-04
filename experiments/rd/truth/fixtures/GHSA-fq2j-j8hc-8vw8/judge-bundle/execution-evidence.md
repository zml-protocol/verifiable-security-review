# Execution evidence (observed facts) — GHSA-fq2j-j8hc-8vw8

Observed behaviour of the two revisions under one identical input. These are facts only; no
conclusion is drawn about which program point is the entry or the behaviour — that is what you
adjudicate.

- Build: each revision built from its checkout with `go build --tags fts5`; the advisory's PoC
  request issued identically against both.
- Input (one request, authenticated): `POST /api/lute/html2BlockDOM` with JSON body
  `{"dom": "<p><a href=\"file:///etc/passwd\">x</a></p>"}`.

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| `html2BlockDOM` response | contains an `assets/<name>` path | contains no `assets/...` path |
| `GET /assets/<name>` | HTTP 200, 1163 bytes, byte-identical to `/etc/passwd` | n/a (no asset path returned) |
| workspace `data/assets/` | a copy of the target file is written | nothing written; the DOM keeps `data-href="file:///etc/passwd"` |

Same input, effect observed on the vuln revision and not on the fixed revision.
