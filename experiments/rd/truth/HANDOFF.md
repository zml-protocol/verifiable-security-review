# RD C.4 fixture-truth — handoff to continue (2026-10-03)

You are taking over RD §15 **C.4: building blind, three-way-adjudicated ground truth** for the fresh
fixtures, one fixture at a time, to truth-freeze. Go is CLOSED at N=3. **Python is next, starting at
LiteLLM #1 (not yet authored).** Everything below is the operating contract; follow it exactly.

Repo: `/home/yuzuki/WF/secreview`. Branch `main`. Python env via `uv run python`. Git clean except
untracked `blog/`.

## 0. Non-negotiable frozen rules (do NOT drift)
- **§15 charter is frozen**; the truth tooling is frozen (HC-1 was the last allowed wiring fix). From
  here, a fixture that is "hard to express" (matcher can't express an equivalence, a relation/qualifier
  doesn't fit, a behavior spans branches) is a **measurement result**, NOT a tooling change. The only
  permitted code change is a pure implementation bug under the frozen harness-change rule — and you
  should surface it before acting.
- **Author truth is immutable once any judge has seen the bundle.** No "judge revealed the right
  anchor → fix truth → resubmit." A late-found anchor error stands as INDETERMINATE/inadmissible.
- **Anchor self-review (`ANCHOR-SELF-REVIEW.md`) is mandatory BEFORE building the bundle / running any
  judge.** Anchors are statement-granularity per EN/BE/AC — not whole functions, not sub-expressions.
  Two Go fixtures (oh-my-posh entry, fabric-ca context) were lost to author anchor-granularity errors;
  do not repeat them.
- **Three-way admissibility** (`agreement.check`): an item author-expected REQUIRED is admissible only
  if BOTH judges say REQUIRED; else INDETERMINATE. If **entry OR behavior** is INDETERMINATE → fixture
  **inadmissible** → `§15.2` substitute the next reserve of the same language (must still satisfy the
  CWE per-class ≤2 quota). **Reserves exhausted → reduce N, no backfill** (no re-screening, no
  quota-skipped promotion, no rescue). Distractors must be NOT_REQUIRED by both.
- **Judges** (truth adjudicators, independent of the author): A = `gpt-6.1-sol` (Codex CLI),
  B = `deepseek/deepseek-flash` (OpenCode CLI). Operator confirmed the ChatGPT account used by Codex
  has **Memory + Custom Instructions OFF**. Run them yourself via `run_judges.sh` (isolation baked in).
- **Judges use canonical `vuln`/`fixed`** revision labels and may see the fix diff + advisory + execution
  facts. The seed-mapped agent-facing `revision_A/B` (`revision_map.py`) is ONLY for the eventual
  evaluated agent — NOT for adjudication.
- **Never give a judge** (nor the evaluated agent, ever): `requirement-truth.yaml`, `sheet-key.yaml`,
  `advisory-redaction-log.md`, selection `decision.md`, probe source / executor reasoning, verifier/
  scorer output, this project's chat, or the other judge's output. Judges get ONLY `judge-prompt.md`
  (self-contained, leak-checked, opaque item ids, fact-only advisory).

## 1. State tally
- **Infra frozen**: selection queue (`2437b85`), truth tooling (`3b474e8`), HC-1 wiring (`301e93d`),
  judge harness (`8705809`). `results/rd-queue.yaml` is the frozen ordered queue; `results/
  rd-selection-log.jsonl` is the append-only selection log (do not edit). `truth-tooling-freeze.json`
  pins matcher/vocab/provider/pool/seed/tool hashes; `freeze.verify_freeze()` gates `build_sheet`.
- **Go — CLOSED at N=3**: FROZEN admissible = SiYuan `GHSA-fq2j-j8hc-8vw8`, Vikunja
  `GHSA-mr3j-p26x-72x4`, DHCP `GO-2026-6237`. Inadmissible = flagd `GHSA-rmrf-g9r3-73pm` (behavior
  INDETERMINATE, BE-3 two-branch), oh-my-posh `GHSA-fwjx-9p69-h25h` (entry INDETERMINATE), fabric-ca
  `GHSA-xghw-p77p-3r7x` (behavior INDETERMINATE, author context-anchor error). Reserves exhausted.
- **Python — NOT started.** Frozen queue: primary = `GHSA-hx8v-g79f-8w5f` (litellm),
  `PYSEC-2026-1868` (reflex), `GHSA-xmfj-7pp5-fxr6` (llama-stack), `GHSA-5gfj-64gh-mgmw` (agixt);
  reserve = `GHSA-xcw4-53cc-hv32` (mnemosyne), `GHSA-937x-gpqr-72gg` (flask-reuploaded). Target N=4.
- **Realized total** likely **7** (Go 3 + Python ≤4). Final report must list planned N=8 → realized N
  with per-fixture reasons (two Go reserve losses were author anchor errors — recorded honestly).

## 2. Per-fixture workflow (repeat for each Python primary, strict queue order)
Let `ID` = fixture id, `D = experiments/rd/truth/fixtures/$ID`, `T = runs/rd/precheck/$ID/trees`
(has `parent/` and `fix/` checkouts). `decision.md`, `facts.json` (changed files + parent sha),
`supplemental-confirmation.md` (if any) are under `runs/rd/precheck/$ID/`. The advisory is read via
the gated reader (see §3). Selection evidence: `results/rd-selection-log.jsonl` (the `decide` entry).

1. **Gather**: read `facts.json` (parent sha, changed files), the `decide` evidence, and
   `git -C $T/fix diff <parent> <fix> -- '<non-test .py/.go>'` to see the fix. Read the advisory.
2. **Author `executable-truth.md`** (author-side; the input→effect flip from selection/supplemental
   evidence; names the canonical vuln=parent / fixed=fix commits).
3. **Author `requirement-truth.yaml`** (canonical `vuln`/`fixed` slots; anchors `{file,start_line,
   end_line,expression}`). entry (EN), behavior (BE), optional admissible qualifiers; anything
   security-related-but-not-claim-necessary or outside the frozen qualifier vocab → `non_scored_notes`
   (NOT a scored item, NOT UNSUPPORTED_REQUIREMENT_TYPE unless it is a *required* item the vocab can't
   express). See a frozen example: `fixtures/GHSA-fq2j-j8hc-8vw8/requirement-truth.yaml`.
4. **Self-review** against `ANCHOR-SELF-REVIEW.md` + verify every anchor resolves uniquely:
   `resolver.resolve_identity(anchor, language=…, revision='vuln'|'fixed', source=<file text>)`.
   Statement granularity. Per-revision line numbers (insertions shift lines).
5. **Build the bundle**:
   `uv run python experiments/rd/truth/build_sheet.py $ID --truth $D/requirement-truth.yaml --trees $T --out $D`
   → `adjudication-sheet.yaml` (opaque, 2 real + distractors), `sheet-key.yaml` (author-side answers),
   `code-context/{vuln,fixed}.md`.
   `uv run python experiments/rd/truth/build_evidence.py $ID --out $D/advisory-evidence.md`
   → fact-only advisory (fix-attribution redacted to `advisory-redaction-log.md`, author-side).
   Write `$D/instructions.md` (claim/domain + output schema; copy a frozen one and edit the claim) and
   `$D/execution-evidence.md` (facts only: input, vuln result, fixed result — no "this proves X").
   Assemble `$D/judge-bundle/` = definitions.yaml (copy `experiments/rd/definitions.yaml`),
   instructions.md, adjudication-sheet.yaml, code-context/{vuln,fixed}.md, fix-diff.patch
   (`git -C $T/fix diff <parent> <fix> -- '<non-test>'`), advisory-evidence.md, execution-evidence.md.
   Assemble `$D/judge-prompt.md` = header + all bundle sections inlined + output schema (see any frozen
   fixture's judge-prompt.md as the template; judges have tools off so everything must be inlined).
   **Leak-check** judge-prompt.md: no `author_expected`/`is_distractor`/`real_id`, no real item ids,
   opaque `item-NN` only, advisory section free of fix-attribution prose.
6. **Run judges**: `experiments/rd/truth/run_judges.sh $D` → `judge-a.yaml`, `judge-b.yaml` (+ raw
   transcripts). De-escape any markdown-escaped underscores in the raw paste if needed (format-only).
7. **Reconcile** (map opaque→real via `sheet-key.yaml`, run `agreement.check`): build the author doc
   (sheet items + their `author_expected` from the key), `agreement.check(author, judge_a, judge_b,
   anchor_identity=lambda a:a)`. See any frozen `reconciliation.md` for the exact snippet.
8. **Decide**:
   - entry & behavior three-way admissible, distractors rejected, no two-sided missing → write
     `reconciliation.md` (FROZEN) + add a `PREREGISTRATION.md` change-log row + commit → next fixture.
   - entry OR behavior INDETERMINATE → `reconciliation.md` (INADMISSIBLE) + `§15.2` substitute next
     Python reserve (re-check CWE quota) + PREREG row + commit, then author the substitute. Reserves
     exhausted → reduce N (stop adding Python fixtures), record it.
   - A two-sided missing requirement (both judges propose the same missing item by full identity) is
     `INCOMPLETE_TRUTH_SPEC`: the author may revise once and re-adjudicate with two NEW judge sessions
     (this is the ONE revision path the charter allows — see §15.1). A one-sided missing is only an
     ambiguity-burden note.
9. Do NOT batch-author all Python fixtures then adjudicate; do one fully to freeze/inadmissible first.

## 3. Tool / path reference
- Frozen truth tooling (`experiments/rd/truth/`): `matcher.py` (`node_identity`, frozen syntax-node
  identity; provenance `matcher-provenance.json`), `resolver.py` (anchor {file,line,expr}+rev+source →
  node_identity; whole-line, indentation-tolerant, internal-exact, unique-or-fail-loud),
  `anchor_machinery.py` (distractor callbacks), `revision_map.py` (seed map — agent only),
  `agreement.py` (`check`), `distractors.py`, `vocabulary.py` (allowed qualifier kinds = guard/config/
  dispatch_target; `is_admissible`), `freeze.py` (`verify_freeze`). Operational: `build_sheet.py`,
  `build_evidence.py`, `run_judges.sh`. Discipline: `ANCHOR-SELF-REVIEW.md`. Changelog:
  `HARNESS-CHANGES.md`.
- Definitions shown to judges: `experiments/rd/definitions.yaml` (EN/BE/AC/qualifier rules, verbatim).
- Advisory (gated reader): `PYTHONPATH=experiments/fieldwork:experiments/rd uv run python -c "import
  rd_precheck; print(rd_precheck.advisory_record({'id':'<ID>'}))"` (runs the conformance gate).
- Per-fixture dir `experiments/rd/truth/fixtures/<ID>/`: executable-truth.md, requirement-truth.yaml,
  judge-bundle/, judge-prompt.md, sheet-key.yaml, judge-a.yaml, judge-b.yaml, reconciliation.md.

## 4. LiteLLM #1 — exact next step (authoring in progress; nothing written yet)
- `ID=GHSA-hx8v-g79f-8w5f`, berriai/litellm, **SSRF**. vuln=parent `93faf321df159b1ef65a98cc29a70958a96d184a`,
  fixed=fix `47214be317f45a2d2ac08258362e0481411eb427`. Route PROBE (TEST did not cover the guard).
- **The vuln**: the proxy request-body guard `is_request_body_safe` (litellm/proxy/auth/auth_utils.py)
  bans top-level `api_base`/`base_url` but NOT a `user_config` nested `api_base`, allowing SSRF (the
  attacker steers the upstream base URL). PROBE: `is_request_body_safe({"model":…,"user_config":
  {"api_base": "http://attacker/steal"}}, …)` → parent returns True (accepted); fix raises ValueError
  "user_config is not allowed in request body".
- **Proposed anchors (verify via self-review + resolver; Python `ast`)**:
  - entry (EN-1): the attacker-controlled request body = the `request_body` parameter of
    `is_request_body_safe` (litellm/proxy/auth/auth_utils.py, `def is_request_body_safe(` at parent
    L144). Present both revisions.
  - behavior (BE-1, a **changed check**, present at BOTH revisions, content changed): the banned-params
    list the guard enforces — parent L153 `banned_params = ["api_base", "base_url"]`, fix L153
    `banned_params = ["api_base", "base_url", "user_config"]`. State present/present; the matcher
    identities differ by content_digest. (Confirm the `for param in banned_params:` loop at L155 reads
    it; the behavior is the changed check that decides rejection.)
  - The other 4 changed files (`_internal_context.py`, `litellm_pre_call_utils.py`,
    `emulated_handler.py`, `utils.py`) are the same-commit internal-call refactor ("H15") and are NOT
    the SSRF check → `non_scored_notes`. Verify this before finalizing (don't let a refactor masquerade
    as the behavior).
- Then: self-review → build_sheet/build_evidence → assemble bundle+prompt → leak-check → run_judges.sh
  → reconcile → freeze or inadmissible. Note: litellm per-side venvs exist
  (`runs/rd/precheck/$ID/venv-{parent,fix}`) if you need to re-run the probe, but you should not need to.

## 5. Provenance conventions
- Commit each fixture's freeze/inadmissibility separately; add a `PREREGISTRATION.md` change-log row
  (bottom table) describing the three-way result and disposition. Keep selection log/queue/script
  untouched. `runs/` is gitignored (operator artifacts); `experiments/rd/truth/fixtures/` is tracked.
- Judge raw transcripts (`judge-a.raw.txt`, `judge-b.raw.txt`) are the audit record — keep them.
- Commit attribution trailer is set per the session's current reminder; match it.

## 6. Lessons / watch-list
- The failures cluster on the HARD dimensions: multi-branch/spread behavior (flagd → BE-3 INDETERMINATE)
  and coarse/sub-statement anchors (oh-my-posh entry, fabric-ca context). For each Python fixture:
  (a) if the fix spans several files/branches, ask whether the behavior is a single orderable check
  (BE-3) before authoring; (b) anchor entry/behavior/context at the exact statement the rule names.
- LiteLLM and llama-stack are spread fixes — apply the BE-3 check carefully. reflex/agixt/mnemosyne/
  flask-reuploaded unseen — gather first.
