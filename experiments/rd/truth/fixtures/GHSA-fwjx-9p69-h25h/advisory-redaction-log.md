# Author-side redaction log — GHSA-fwjx-9p69-h25h (NOT given to judges)

Lines removed from the advisory details as fix-attribution:

- Suggested fix: neutralize C0/C1 control characters in untrusted segment data before it reaches the terminal, at minimum the path segment (folder names) and the git segment (`Commit.Subject`, `Commit.Author.*`, `RawUpstreamURL`). `trimAnsi` already exists and is applied to the title; extending equivalent handling to segment data closes the gap. Filtering control runes in `write(s rune)` would also work as defense in depth (Oh My Posh's own styling never flows through that function), optionally behind an opt-out for users who deliberately embed escapes in their own templates.

References removed as fix-locating:

- WEB: https://github.com/JanDeDobbeleer/oh-my-posh/commit/edcf3c88f3fb582e84358b385c49d33d04c04224
