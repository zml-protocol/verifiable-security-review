# Execution evidence (observed facts) — GHSA-hx8v-g79f-8w5f

Observed behavior of the two revisions under identical offline calls. Facts only; no conclusion is
drawn about which program point is the entry or behavior.

- Input body: `{"model":"rd-model","user_config":{"api_base":"http://127.0.0.1:9999/steal"}}`.
- Method: the same single-file offline probe called `is_request_body_safe` at both revisions. It made
  no network request.

Observed results:

| case | vuln revision | fixed revision |
|---|---|---|
| body with no banned parameter | accepted (`True`) | accepted (`True`) |
| body with top-level `api_base` | rejected (`ValueError`) | rejected (`ValueError`) |
| body with nested `user_config.api_base` | accepted (`True`) | rejected (`ValueError`: `user_config is not allowed in request body`) |

The advisory evidence separately states that LiteLLM uses an admitted `user_config` object to build
the outbound router and that its nested `api_base` can select an arbitrary host.
