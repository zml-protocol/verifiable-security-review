# Executable truth — GHSA-hx8v-g79f-8w5f (LiteLLM)  [author-side only]

**Not agent-facing.** This is the §15.3 executable ground truth for the first Python fixture.

- Fixture: `GHSA-hx8v-g79f-8w5f` · repo `berriai/litellm` · language python · Python primary #1 ·
  CWE-918 Server-Side Request Forgery.
- Canonical revisions: **vuln = parent** `93faf321df159b1ef65a98cc29a70958a96d184a`;
  **fixed = fix** `47214be317f45a2d2ac08258362e0481411eb427`.
- Selection route: **PROBE**. The fix revision's changed test file did not cover this request-body
  guard, and the advisory supplied no PoC.

## Triggering input

An authenticated proxy request body containing:

```json
{"model":"rd-model","user_config":{"api_base":"http://127.0.0.1:9999/steal"}}
```

The authenticated caller controls the request body, including the `user_config` object and its
nested `api_base`. The advisory states that LiteLLM uses that object to build a per-request outbound
router, allowing the caller to choose an internal or external destination.

## Observed revision flip

The same offline probe called `is_request_body_safe` with the same triggering body at both
revisions. It made no network request.

| case | vuln revision | fixed revision |
|---|---|---|
| no banned parameter | accepted (`True`) | accepted (`True`) |
| top-level `api_base` | rejected (`ValueError`) | rejected (`ValueError`) |
| nested `user_config.api_base` | **accepted (`True`)** | **rejected (`ValueError`: `user_config is not allowed in request body`)** |

Thus the vulnerable revision admits the attacker-controlled per-request router configuration, while
the fixed revision rejects the identical body at the request-safety guard. The advisory supplies the
downstream security fact: an admitted `user_config.api_base` steers the proxy's outbound request.

## Provenance

- Selection decision: `runs/rd/precheck/GHSA-hx8v-g79f-8w5f/decision.md`.
- Raw observations: `probe-parent.log` and `probe-fix.log` in the same precheck directory.
- Frozen selection log: the `decide` record for this fixture has verdict `ACCEPTED`, route `PROBE`,
  hash `7b86f5a5a5217462c33e71d9c0d3423d087edd6b13b54e6835424f40162c22c3`.

## Scope

This file fixes only the observed input/result flip and its advisory-backed security effect. Entry,
behavior, and any necessary qualifiers are authored separately and must pass blind adjudication.
