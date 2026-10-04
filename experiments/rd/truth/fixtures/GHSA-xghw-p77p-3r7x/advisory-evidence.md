# Advisory factual evidence — GHSA-xghw-p77p-3r7x

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-xghw-p77p-3r7x  (aliases: CVE-2026-53658, GO-2026-6234)
- Affected package: Go: github.com/hyperledger/fabric-ca
- Severity: CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N
- Published: 2026-08-14T19:24:57Z
- Summary: Fabric CA Developer's Guide: LDAP Injection via Unescaped Username in GetUser Filter
- Source: https://github.com/hyperledger/fabric-ca/security/advisories/GHSA-xghw-p77p-3r7x

## Details (verbatim, fix-attribution lines removed)

When fabric-ca is configured with an LDAP backend, the username from HTTP Basic authentication is included in an LDAP uid search filter without proper escaping. An unauthenticated attacker with network access to the CA enrollment endpoint could exploit this to perform LDAP injection before password validation, and potentially steer authentication attempts toward a victim account.

### Recommendation

- All users of fabric-ca with an LDAP backend should update to a fixed version.
- For users not using an LDAP backend, no action is required.

## References (fix-commit excluded)
- WEB: https://github.com/hyperledger/fabric-ca/security/advisories/GHSA-xghw-p77p-3r7x
- PACKAGE: https://github.com/hyperledger/fabric-ca

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
