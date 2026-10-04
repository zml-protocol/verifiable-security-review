# Executable truth — GHSA-fq2j-j8hc-8vw8 (SiYuan)  [DRAFT, pending Codex review; author-side only]

**Not agent-facing.** This is §15.3 executable ground truth: for one triggering input, the
security-relevant effect occurs at the vulnerable revision and not at the fixed revision. The
evaluated RD agent never sees this file, the advisory answer content, or the selection reproduction
artifacts. Judges see it only when adjudicating the requirement truth (§15.1).

- Fixture: `GHSA-fq2j-j8hc-8vw8` · repo `siyuan-note/siyuan` · language go · queue role go primary #1.
- Revisions (truth-side names): **base = parent (vulnerable)** `b0c770c394619dfb645bbcfabbe64dce81b50949`;
  **head = fix (patched)** `294b8b429dea152cd1df522cddf406054c1619ad`.
  (The agent receives seed-mapped neutral revision names per §15.5; those are not used here.)

## Triggering input (one request)

`POST /api/lute/html2BlockDOM` with JSON body `{"dom": "<p><a href=\"file:///etc/passwd\">x</a></p>"}`
and a valid API token. The attacker controls the `dom` field; the embedded `href` names a local
absolute path (`file:///etc/passwd`) on the server host.

## Security-relevant effect (what the executable truth measures)

The handler walks the submitted HTML and, for a node whose resolved local path points at a server
file, copies that file into the workspace assets directory and returns an `assets/...` path by which
its bytes are retrievable over HTTP — i.e. arbitrary local file read / information exposure. The
effect is observed as: (a) a non-empty `asset_paths` in the `html2BlockDOM` response, and (b) a
subsequent `GET /assets/<copied>` returning bytes identical to the targeted server file.

## Base/head flip (established; same input both sides)

| | base (parent, vulnerable) | head (fix, patched) |
|---|---|---|
| `html2BlockDOM` response | `asset_paths: ["assets/passwd-20261002132027-94vut46"]` (http 200, code 0) | `asset_paths: []` (http 200, code 0) |
| `GET /assets/<copied>` | http 200, 1163 bytes, **identical to `/etc/passwd`** | n/a — no asset written |
| on-disk `data/assets/` | byte-identical copy of `/etc/passwd` present | nothing written; DOM keeps `data-href="file:///etc/passwd"` |

Effect **present at base, absent at head**, under one identical request → executable truth
established.

## Provenance (frozen selection evidence; re-recorded, not re-run by the author)

- Built each side with the repo's build files: `go build --tags fts5` (kernel refuses to boot
  without the `fts5` tag). Kernels started on pre-created workspaces; the probe is the advisory's
  inline PoC run identically on both revisions.
- Reproduction artifacts (author-side, non-agent): `runs/rd/precheck/GHSA-fq2j-j8hc-8vw8/decision.md`,
  `poc_siyuan_advisory.py`, `poc-parent.log`, `poc-fix.log`.
- Selection disposition: `decide` verdict **ACCEPTED**, append-only log entry hash
  `65acaf03228fab508...` (route logged `POC`). Per manual checkpoint #2, an advisory-Details-embedded
  PoC is re-described as route `PROBE` going forward; the behaviour flip and admissibility are
  unchanged and the existing log entry is not rewritten.

## Scope note (what is NOT decided here)

This artifact fixes only the input→effect flip. The requirement truth (entry / behavior anchors and
qualifiers, §15.3–§15.4) is authored separately in `requirement-truth.yaml` and is what the two
fresh judges adjudicate; nothing here pre-labels those anchors.
