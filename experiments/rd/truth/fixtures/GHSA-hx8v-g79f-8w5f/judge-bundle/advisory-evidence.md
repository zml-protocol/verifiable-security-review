# Advisory factual evidence — GHSA-hx8v-g79f-8w5f

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-hx8v-g79f-8w5f  (aliases: CVE-2026-59823, PYSEC-2026-4070)
- Affected package: PyPI: litellm
- Severity: CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:N/VA:N/SC:L/SI:N/SA:N
- Published: 2026-09-17T14:51:21Z
- Summary: LiteLLM Proxy has server-side request forgery via the `user_config` request parameter
- Source: https://github.com/BerriAI/litellm/security/advisories/GHSA-hx8v-g79f-8w5f

## Details (verbatim, fix-attribution lines removed)

### Summary
A server-side request forgery in LiteLLM Proxy lets an authenticated caller redirect the
proxy's outbound request to a host of their choosing by smuggling an `api_base` inside the
`user_config` request body, bypassing the existing parameter guard.

### Details
LiteLLM Proxy validates request bodies with `is_request_body_safe`, which blocks the
`api_base` and `base_url` parameters but does not cover `user_config`. The `user_config`
object is used to build the outbound router for a request, so a caller can place an
`api_base` inside it and reach an arbitrary host. The guard only inspected the two
top-level keys, so the same `api_base` nested inside `user_config` was never checked.

Exploitation requires a valid virtual key.

### Impact
An authenticated caller can make the proxy issue server-side requests to internal or
external hosts of their choosing, reaching endpoints the caller cannot otherwise access.

Affected: `<= 1.83.8`

Upgrade to 1.83.9 or later (released 2026-04-17).

## References (fix-commit excluded)
- WEB: https://github.com/BerriAI/litellm/security/advisories/GHSA-hx8v-g79f-8w5f
- ADVISORY: https://nvd.nist.gov/vuln/detail/CVE-2026-59823
- WEB: https://github.com/BerriAI/litellm/pull/25827
- PACKAGE: https://github.com/BerriAI/litellm

## Redaction note
- 3 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
