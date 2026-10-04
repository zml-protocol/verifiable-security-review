# Author-side redaction log — GHSA-xcw4-53cc-hv32 (NOT given to judges)

Lines removed from the advisory details as fix-attribution:

- ### Patched versions
- The fix in v3.10.1 replaces the broken decode with a from-scratch HS256 verifier using only the Python standard library:
- ### Mitigation
- None. The patch is required to restore authentication integrity.

References removed as fix-locating:

- WEB: https://github.com/mnemosyne-oss/mnemosyne/commit/a0b6b8711a1a485304971710dc3571e29ff9dbeb
