# Executable truth — GHSA-xghw-p77p-3r7x (hyperledger/fabric-ca)  [author-side only]

**Not agent-facing.** §15.3 executable ground truth. This fixture is the §15.2 reserve substituted
in for oh-my-posh (which was inadmissible: entry INDETERMINATE); it is the last Go reserve.

- Fixture: `GHSA-xghw-p77p-3r7x` · repo `hyperledger/fabric-ca` · language go · CWE injection
  (LDAP injection) · promoted from go reserve #7.
- Revisions: **vuln = parent** `489a658619140e5332c8e72632037728564a3173`;
  **fixed = fix** `d379df823534d56dec0166a6da8f0415e3beee24`.

## Triggering input (one lookup)

An authentication username containing an LDAP filter metacharacter — e.g. `rd*probe` (a `*`) — passed
to `Client.GetUser`, which interpolates it into the configured LDAP user filter and searches.

## Security-relevant effect

The username is placed into the LDAP search filter **unescaped**, so filter metacharacters change
the filter's meaning: `rd*probe` yields a **wildcard substring filter** `(uid=rd*probe)` (the `*`
acts as an LDAP wildcard) instead of a literal equality match — LDAP injection.

## Base/head flip (established; same input both sides)

| | vuln (parent) | fixed |
|---|---|---|
| `GetUser("rd*probe")` emitted LDAP filter (captured BER) | wildcard substring filter: `initial "rd"` + `any "probe"` (i.e. `(uid=rd*probe)`, `*` = wildcard) | equality match on the literal value `rd*probe` (wildcard structure absent) |

Effect **present at vuln, absent at fixed**, same input → executable truth established.

## Provenance (frozen selection evidence; re-recorded, not re-run by the author)

- Selection `decide`: verdict **ACCEPTED**, route **TEST** — the fix commit's test applied to both
  revisions: fix `go test ./lib/server/ldap/...` exit 0 (`TestUsernameEscape` asserts an escaped
  filter for `*,(,),\`); parent exit 1 **build-fail** (`cannot use *ConnectionStub as *ldap.Conn`),
  because the fix's test depends on the fix's stubbable `Connection` interface.
- **Supplemental PROBE** (checkpoint): identical `GetUser("rd*probe")` against a local capture
  server on both revisions; the captured SearchRequest BER shows parent = wildcard substring filter,
  fix = literal equality filter. Behaviour flip established true.
- Reproduction artifacts (author-side): `runs/rd/precheck/GHSA-xghw-p77p-3r7x/decision.md`,
  `supplemental-confirmation.md`, `supplemental-parent.log`, `supplemental-fix.log`.

## Scope note

Fixes only the input→effect flip. Entry/behavior anchors are authored in `requirement-truth.yaml`.
