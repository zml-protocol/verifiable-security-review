# Execution evidence (observed facts) — GHSA-xcw4-53cc-hv32

Observed behavior of the two revisions under identical regression-test inputs. Facts only; no
conclusion is drawn about which program point is the entry or behavior.

- Setup: a local HTTP server on `127.0.0.1` using `SyncHTTPHandler`, with `api_key = None` and
  `jwt_secret = "test-secret"`.
- Triggering request: `GET /sync/status` with an `Authorization: Bearer <token>` header. The token
  has a JSON-object header `{"alg":"HS256","typ":"JWT"}`, a JSON-object payload with
  `{"sub":"attacker","exp":<one hour in the future>}`, and the literal signature `forged`,
  which was not computed from `test-secret`.
- Method: the fix revision's JWT regression tests were applied unchanged to both revisions.

Observed results:

| case | vuln revision | fixed revision |
|---|---|---|
| well-formed HS256 token with forged signature | HTTP 200 | HTTP 401 (`invalid JWT signature`) |
| token with `alg: none` and forged signature | HTTP 200 | HTTP 401 (`unsupported JWT algorithm`) |
| token with malformed non-ASCII signature | HTTP 200 | HTTP 401 (`invalid JWT signature`) |
| valid HS256 token | HTTP 200 | HTTP 200 |
| expired validly signed token | HTTP 401 | HTTP 401 |

The complete JWT test selection reported `3 failed, 2 passed` at the vulnerable revision and
`5 passed` at the fixed revision. The three vulnerable-revision failures are the first three rows,
where the tests expected rejection but received acceptance.

The advisory evidence separately states that accepted JWT authentication permits access to
`/sync/status`, `/sync/push`, and `/sync/pull`, including reads and modifications of sync data.
