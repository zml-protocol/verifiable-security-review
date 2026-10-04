# Execution evidence (observed facts) — GO-2026-6237

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input: a UDP/IPv4 frame delivered to `BroadcastRawUDPConn` whose IPv4 header declares an IP payload
  length smaller than a UDP header (8 bytes) — e.g. a declared payload length of 0.
- Method: the fix commit's regression test applied to both revisions (go1.26.8, `-mod=readonly`),
  `go test ./dhcpv4/nclient4/...`.

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| short-IP-payload frame | test exits non-zero: panic `slice bounds out of range [:-8]` in `buf.Consume` | test passes: the short frame is discarded and reading continues |

Same input, the panic occurs on the vuln revision and not on the fixed revision.
