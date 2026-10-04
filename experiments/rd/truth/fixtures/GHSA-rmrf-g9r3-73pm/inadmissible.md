# flagd (GHSA-rmrf-g9r3-73pm) — INADMISSIBLE (behavior INDETERMINATE_TRUTH); reserve substituted

go-primary queue position #3. **Not frozen as a fixture truth.** The requirement behavior is
`INDETERMINATE_TRUTH` under the frozen §15.3 rule BE-3, so by §15.1 the fixture is inadmissible and
is replaced from the Go reserve queue under §15.2.

## Why behavior is INDETERMINATE (BE-3)

The fix enforces the request-body-size limit — the security-relevant check for this
resource-consumption claim — at **two independent service-setup branches**, each deciding the
oversized-body effect for its own endpoint with the same mechanism but a different response:

- OFREP service (`flagd/pkg/service/flag-evaluation/ofrep/ofrep_service.go`):
  `if cfg.MaxRequestBodyBytes > 0 { h = http.MaxBytesHandler(h, cfg.MaxRequestBodyBytes) }`
  (+ handler.go maps `*http.MaxBytesError` → HTTP 413).
- connect service (`flagd/pkg/service/flag-evaluation/connect_service.go`):
  `http.MaxBytesHandler(svcHandler, svcConf.MaxRequestBodyBytes)` → connect `resource_exhausted` (429).

These are two changed checks on different branches (different endpoints) that each decide the effect
and cannot be ordered "nearest the effect" for a single claim covering the package. BE-3: the
behavior is `INDETERMINATE_TRUTH` and the fixture is replaced.

## Distinction from the supplemental confirmation

The earlier supplemental PROBE confirmed the **executable-truth flip** (a 2.1 MB body: vuln 200 →
fix 413 OFREP / 429 connect), which is real and unchanged. That is §15.3 executable truth. The
present finding is about the §15.3 **requirement behavior anchor**, which is indeterminate across the
two branches. Executable-truth flip holding does not make the requirement behavior determinate.

## Disposition (§15.2 substitution)

- flagd is dropped from the admissible set (behavior INDETERMINATE). The frozen selection queue is
  unchanged (append-only); this substitution is a truth-phase event recorded here and in the
  PREREGISTRATION change-log.
- Next Go reserve promoted: **oh-my-posh (`GHSA-fwjx-9p69-h25h`, CWE-150, reserve #6)**. CWE-class
  quota re-checked (per_cwe_class ≤ 2 holds): new go-primary set = SiYuan, Vikunja, DHCP, oh-my-posh.
- No judges were run for flagd (no single determinate behavior to adjudicate); this is an
  author-side BE-3 determination, operator-approved.
