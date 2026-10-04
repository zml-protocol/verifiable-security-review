# Executable truth — GO-2026-6237 (insomniacslk/dhcp)  [author-side only]

**Not agent-facing.** §15.3 executable ground truth: for one triggering input, the security-relevant
effect occurs at the vulnerable revision and not at the fixed revision.

- Fixture: `GO-2026-6237` · repo `insomniacslk/dhcp` · language go · queue role go primary #4.
- Revisions: **vuln = parent** `a415979eb11e6d3ac6a8949f9e45d7a29f0279af`;
  **fixed = fix** `c76316d4aa825673b208730779843d0711021e81`.

## Triggering input (one frame)

A crafted UDP/IPv4 frame received on `BroadcastRawUDPConn` whose IPv4 header declares an IP payload
length smaller than a UDP header (`udpMinimumSize`, 8 bytes) — e.g. a declared payload length of 0.
The attacker controls the bytes delivered to the raw packet connection.

## Security-relevant effect

`ReadFrom` computes `dhcpLen = payloadLength - udpHdrLen`; for a declared payload length below the
UDP header length this is **negative**, and `buf.Consume(dhcpLen)` then slices with a negative
length, causing a runtime panic ("slice bounds out of range"). A reachable panic on attacker input
is a denial of service.

## Base/head flip (established; same input both sides)

| | vuln (parent) | fixed |
|---|---|---|
| short-IP-payload frame (declared payload length < 8) | `buf.Consume(dhcpLen)` panics `slice bounds out of range [:-8]` | the frame is discarded (`continue`); no panic; `ReadFrom` proceeds to the next frame |

Effect **present at vuln, absent at fixed**, same input → executable truth established.

## Provenance (frozen selection evidence; re-recorded, not re-run by the author)

- Selection `decide`: verdict **ACCEPTED**, route **TEST** — the fix commit's regression test
  (`dhcpv4/nclient4/conn_unix_test.go`: `TestReadFromShortIPv4Payload`, `...SkipShortFrameThenReadsNext`)
  applied to both revisions (go1.26.8, `-mod=readonly`): fix `go test ./dhcpv4/nclient4/...` exit 0;
  parent exit 1 with panic `slice bounds out of range [:-8]` on the payload-0 case.
- Reproduction artifacts (author-side): `runs/rd/precheck/GO-2026-6237/decision.md`,
  `test-parent.log`, `test-fix.log`.

## Scope note

Fixes only the input→effect flip. Entry/behavior anchors are authored in `requirement-truth.yaml`.
