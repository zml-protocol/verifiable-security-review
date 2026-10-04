# Advisory factual evidence — GO-2026-6237

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GO-2026-6237  (aliases: )
- Affected package: Go: github.com/insomniacslk/dhcp
- Severity: 
- Published: 2026-08-18T16:38:10Z
- Summary: Denial of service via malformed IPv4 packet in github.com/insomniacslk/dhcp
- Source: https://github.com/insomniacslk/dhcp/commit/c76316d4aa825673b208730779843d0711021e81

## Details (verbatim, fix-attribution lines removed)

In github.com/insomniacslk/dhcp/dhcpv4/nclient4, BroadcastRawUDPConn.ReadFrom does not validate that the IPv4 payload length is sufficient to hold a UDP header before calculating the DHCP payload length. A frame with an IPv4 total-length field specifying fewer than eight payload bytes results in a negative DHCP length, causing a panic in buf.Consume due to a negative slice bound.

## References (fix-commit excluded)

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
