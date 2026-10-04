# Fieldwork: one real, disclosed finding

Goal: at least one maintainer-acknowledged OSS vulnerability (GitHub advisory / CVE) from the
RD candidate pool, for the AppSec job portfolio. Rules:

- This is **personal fieldwork**, not part of the frozen RD protocol. It reads the public pool
  and OSV snapshot only; it never writes under `results/` or `runs/rd/`, never touches
  `selection.py` / the pool / the log.
- Local reproduction only. Never test against third-party production or someone else's instance.
- Responsible disclosure: private GitHub Security Advisory first, CVE requested by the
  maintainer/GitHub; nothing public before a fix ships.
- **Disclosure gate: no report is submitted anywhere without the user's explicit review and
  approval of the finding, the repro, and the report text.** This agent prepares; the user submits.
- Acceptance bar: maintainer confirms the report (advisory / CVE / bounty). "Looks buggy" is
  not a finding.

## Pipeline

- `rank_targets.py` — pool → GitHub metadata (stars, archived, pushedAt). Output:
  `.cache/fieldwork/ranked.json` (381 repos pass: ≥300 stars, unarchived, AppSec-relevant class).
- `fetch_diffs.py <owner/repo>` — fix-commit patches via the commits API, cached under
  `.cache/fieldwork/diffs/<owner__repo>/<id>.json`, with a heuristic "added decision lines" score.
- `scan_fastapi_auth.py <backend-root>` — AST scan of FastAPI handlers; reports handlers without
  a visible auth signal so a human can triage them against intentional-public routes and
  in-handler auth.
- `provenance.jsonl` — one line per screened lead: how the pipeline surfaced it (pool rank /
  diff screen / scanner), the method used, and the outcome. Every future finding must cite its
  provenance here so the pipeline's contribution is auditable, never claimed in prose.
- `sarif_triage.py <file.sarif> [top]` — CodeQL SARIF triage: counts per rule and the
  highest-security-severity results with locations.
- `rd_precheck.py <candidate-id> [...]` — mechanical pre-check for the RD manual admissibility
  step. `candidate()` runs `selection.checked()` (script/pool/log-chain) **before** the pool is
  read, so no candidate commit is touched before the provenance gate; the snapshot comes only from
  `selection.open_snapshot()` (conformance gate + manifest). Writes
  `runs/rd/precheck/<id>/{facts.json,summary.md}` including the script/pool hashes and log head.
  Facts only — the manual checker still reads, reproduces and runs `decide`.
- `rd_manual_kit.py <candidate-id> [...]` — prepares the manual checker's environment:
  parent/fix worktrees from the cached bare repo, per-side diagnostic builds (Go module located
  under the tree and built with `-mod=readonly`; Python with one editable environment per side so
  neither tree leaks into the other), toolchain versions recorded, and a pre-filled
  `runs/rd/precheck/<id>/decision.md` template. Facts are regenerated through the gated precheck
  instead of trusting a historical `facts.json`. Builds are diagnostic only: they never decide a
  TEST/POC/PROBE verdict.
- Clones for live analysis: `.cache/fieldwork/clones/<name>` (shallow).
- Scratch venvs: `.cache/fieldwork/venvs/`.

## CodeQL pass

The bundle at `.cache/toolchains/codeql-bundle-v2.27.1/codeql` carries the standard query packs.

```bash
CB=$PWD/.cache/toolchains/codeql-bundle-v2.27.1/codeql; export PATH=$CB:$PATH
# Python (no build):
codeql database create .cache/fieldwork/codeql/NAME-db --language=python \
    --source-root=.cache/fieldwork/clones/NAME --overwrite
codeql database analyze .cache/fieldwork/codeql/NAME-db \
    codeql/python-queries:codeql-suites/python-security-extended.qls \
    --format=sarif-latest --output=.cache/fieldwork/codeql/NAME.sarif --threads=8
# Go needs a real build; put the bundled toolchain on PATH first:
PATH=$PWD/.cache/toolchains/go1.26.8/bin:$PATH codeql database create ... --language=go ...
codeql database analyze ... codeql/go-queries:codeql-suites/go-security-extended.qls ...
```

CodeQL is a triage aid: the standard suites have false positives around custom sanitizers, so
every candidate must be read in the code before it counts.

## Screened and ruled out (do not redo)

- **open-webui** (66 fixes): hardened; many commits are themselves residuals of prior CVEs and
  include per-hop SSRF checks, decoder caps, safe clients. Very high effort; deprioritized.
- **changedetection XPath blocklist** (CVE-2026-29039 + json-doc bypass): enumerated every
  IO-capable function in elementpath 5.1.1 source (`urlopen`/`os.environ`/`Path.open`);
  `function-lookup`, expanded QName `Q{}`/`fn:`, and lookup of removed names all fail closed.
  Only `put` is IO-capable and is not parseable. No bypass found.
- **changedetection decorator order** (CVE-2026-35490): AST scan over the current tree found no
  wrapper decorator above any `.route(...)`; a static test now guards it.
- **changedetection SSRF** (CVE-2026-27696): mature; Chromium fetchers' redirect chain is a
  documented known gap (not a finding). Requests fetcher re-checks DNS per fetch and per hop.
- **gradio `safe_join`**: current main normalizes with `posixpath.normpath()` before the checks,
  so embedded `..` and absolute paths are handled.
- **fiber `sanitizePath`**: `pathpkg.Clean` + explicit `..` segment scan + drive/UNC rejection.
- **langflow route auth** (after `Add authentication to various endpoints`, GHSA-c5cp-vx83-jhqx,
  and the IDOR fix GHSA-qrpv-q767-xqq2): `scan_fastapi_auth.py` on the current tree (296
  handlers) leaves 42 without a visible auth signal; every one is intentional-public (health,
  login, public/shared flow build, webhooks, profile pictures, store catalog, folder redirects)
  or authenticates inside the handler (a2a `_enforce_a2a_auth`, MCP `verify_project_auth`,
  MCP bearer middleware). No missing-auth route found. Caveat: per-resource permission
  semantics (`ensure_flow_permission` and friends) were not audited.
- **gogs residual classes**: API label/milestone/issue-label handlers are repo-scoped; deploy
  keys and issue comments already carry the `issue.RepoID`/`key.RepoID` checks; branch deletion
  has no API path and the web guard is exact-name (protection model has no wildcards); Git
  argument injection carries `--end-of-options` on every ref-taking command (merge/rebase/
  checkout) and clone/push/tag use the git-module API; Git HTTP path traversal is blocked by a
  `pathx.Clean` equality check; wiki page names strip slashes after `pathx.Clean`; tag and
  hook-name paths are validated. No residual found.
- **mlflow prompt source**: the current tree does not use the cached (intermediate) fix; prompt
  sources are now restricted to a placeholder allowlist (`_validate_prompt_source`), so the
  schemeless-relative-path gap in the earlier diff is closed upstream.
- **CodeQL-scanned batch** (see `provenance.jsonl` for the per-repo entries): AstrBot
  (operator-configured SSRF, guarded path code), glances (clear-text logging only), OpenList
  (extraction guards verified; remaining taint paths partly traced), copyparty (build-time
  self-extractor and operator templates), 3x-ui (operator-configured certificate checks), agno
  (`eval` replaced by a type map; the generic pickle utility has no callers), mem0 (SafeUnpickler
  on the only pickling store), PraisonAI (CLI guardrails and a sandbox that is not a privilege
  boundary), new-api vs one-api (new-api has a dial-time protected fetch client; the fixed paths
  are new-api features, one-api is dormant without them).
- **Lower-tier batch** (300–3,000 stars): cloudreve's admin write routes all carry
  `ScopeAdminWrite` (no sibling of the fixed scope gaps); ech0's dedicated egress client
  validates the connection address after dialing and each redirect hop, and its only raw HTTP
  client targets a hardcoded host; asyncssh's SCP `C`/`D` messages share the fixed parser;
  oauthlib has no JSONP left; web2py's `prevent_open_redirect` hardening holds for the encodings
  tried; dulwich quotes every merge-driver placeholder; openmeter binds JSON paths as SQL
  parameters; pydicom rejects anchors and out-of-root paths after resolve; daptin's upload and
  unzip sanitizers strip traversal; bugsink's webhook URL check is an ASCII allowlist aligned
  with the requests parser; authorizer normalizes both sides of the origin comparison. The
  ranked small-no-test queue is complete; no finding in this vein.

## Live leads (next)

The first pass over the OSV-window top and mid tier is drying up: those projects are the ones
already receiving active security attention (several fixes are co-authored by AI security
reviewers and cite their own prior CVE residuals). CodeQL standard suites add little there —
their high-severity hits are custom-sanitizer false positives or operator-configured surfaces.

Lower-tier batch complete (300–3,000 stars): cloudreve, ech0, asyncssh, oauthlib, web2py,
dulwich, openmeter, pydicom, daptin, bugsink and authorizer were all audited and ruled out
(see the entry above and `provenance.jsonl`). The fix-completeness vein on the OSV window is
mined out for now.

Next actions:
1. **Fresh-feature audit** (in progress): open-webui's current main was scanned with its auth
   helpers (541 handlers; 25 without a visible signal, all public-by-design, dev-only,
   disabled-by-default, or bound to a session-validated state). langflow's anonymous PUBLIC
   authorization was read (the PR carries principal-binding and boundary tests), and the other
   queued features (id-keyed project upsert, queued-run trace link, telemetry/health exports)
   are security-clean or surface-free. open-webui's event webhooks are admin-only with
   safe-client delivery.
2. **Dynamic testing next**: static review has now cleared four veins (fix residuals, CodeQL
   suites, lower-tier queue, fresh routes). The remaining yield is in running a target locally
   and probing auth logic, races and cache behaviour that static reading cannot see.
3. **Dynamic testing** (started): ech0 was built from the pinned clone with the bundled Go
   toolchain (a stub `template/dist/index.html` is enough for the API; the real frontend build
   is gitignored) and run on 127.0.0.1 with a temp DB. The OpenAPI route/scope map was
   enumerated; `/agent/info` redacts key/prompt/base_url; public settings and connect DTOs carry
   no credentials; a `profile:read` token gets 200 on `/user` and 403 on admin/echo routes; a
   non-admin cannot mint admin-scoped tokens. No finding.
4. **Class shift**: authorization/business logic and HTTP/parser differentials, where the
   standard query packs have poor coverage.
5. **Deep single-target audit**: finish tracing the OpenList path-injection taint paths, or
   pick one mid-tier target and audit its path/auth handling end to end.

## Transfer to RD (what can and cannot feed back)

RD is frozen (`PREREGISTRATION.md` §15). Only the following may cross over, and only outside
`results/` and the hash-chained log:

- **Pre-check tooling for manual admissibility.** Per candidate, extract from the cached bare
  repo (no network, no verdict): the fix-commit file list, test-file presence, non-test added
  lines, and mechanical identifier overlap between the advisory text and the changed test
  files — the "litellm note", mechanized. Output to `.cache/rd/precheck/` or
  `runs/rd/precheck/`; the manual checker still reads, reproduces and runs `decide`.
- **Environment patterns.** Parent/fix worktrees, the bundled Go toolchain
  (`.cache/toolchains/go1.26.8`), uv venv handling — reusable for the manual checks that are
  the current bottleneck.
- **Motivation material for the RD paper.** The ruled-out map plus the public cases (litellm
  test gap, changedetection bypass chain, open-webui residual comments) documents the
  difficulty the RD protocol is built around. Report as field notes, never as a measured result.
- **Nothing selects or reorders.** Star ranking must not touch the seeded queue; changing a
  selection rule requires a new protocol version reviewed by Codex.
- **Disclosure.** The fieldwork read beyond the RD review boundary on litellm and siyuan; flag
  that before any truth authoring touching those fixtures. Blind adjudication bounds the
  impact, but the author's prior reading must be declared.

## Reporting assets

- `gh` is authenticated as `YuzukiS` (repo scope). Reports will be prepared as text + minimal
  repro; submission is under the user's account.
