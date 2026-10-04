# Author-side redaction log — GHSA-fq2j-j8hc-8vw8 (NOT given to judges)

Lines removed from the advisory details as fix-attribution:

- - **Missing check**: The code does not call `util.IsSensitivePath(localPath)` before copying, so any readable file (e.g. `/etc/passwd`, `~/.ssh/id_rsa`) can be copied into assets.
- - **Behavior**: The path is resolved with `model.GetAssetAbsPath("assets" + path)` and the file is served with `http.ServeFile`; any authenticated request (including publish visitors) can access existing asset files.
- // Paths below fall under util.IsSensitivePath prefixes (/etc, c:\windows\system32)

References removed as fix-locating:

- WEB: https://github.com/siyuan-note/siyuan/commit/294b8b429dea152cd1df522cddf406054c1619ad
