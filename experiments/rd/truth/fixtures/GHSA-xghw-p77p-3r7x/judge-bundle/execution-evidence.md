# Execution evidence (observed facts) — GHSA-xghw-p77p-3r7x

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input: `Client.GetUser("rd*probe", ...)` — a username containing an LDAP filter metacharacter (`*`),
  looked up against an identical local capture server on both revisions.
- Method: the same probe on both revisions captures the emitted LDAP SearchRequest (BER bytes); the
  fix commit's test (`TestUsernameEscape`) also applied to both (go1.26.8, `-mod=readonly`).

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| emitted LDAP filter for `rd*probe` | wildcard substring filter: `initial "rd"` + `any "probe"` (`(uid=rd*probe)`, `*` interpreted as a wildcard) | equality match on the literal value `rd*probe` (no wildcard structure) |

Same input, the `*` is interpreted as a filter wildcard on the vuln revision and as a literal on the
fixed revision.
