# Flask-Reuploaded (GHSA-937x-gpqr-72gg) — INADMISSIBLE (entry INDETERMINATE_TRUTH); reserves exhausted

Final Python reserve (position #22), promoted for inadmissible llama-stack. **Not frozen as an
admissible fixture truth.** The executable case-folding bypass and its fixed behavior are
established, but the exact `name` parameter entry cannot be expressed by the frozen whole-line
resolver/matcher. This is a frozen-harness measurement result, not a tooling-change request.

## Executable truth remains established

The fix revision's regression test was applied unchanged to both revisions:

- triggering input: `UploadSet.save(TestingFileStorage(filename="safe.txt"),
  name="backdoor.PHP")` under `AllExcept(SCRIPTS)`;
- vuln (`17509f0bf9436566085a10ad49946c5e5022d3c1`): the call accepts the mixed-case denied extension,
  so the regression test fails because no `UploadNotAllowed` is raised;
- fixed (`5ded76092429c6eb8a4af941b14fbde40a38fff4`): the same call raises `UploadNotAllowed`; the full
  test file reports `52 passed`.

The input/result flip is real. The inadmissibility concerns only §15.3 requirement anchoring.

## Why entry truth is not expressible

The claim's attacker-controlled input is the `name` override passed to the exposed
`UploadSet.save()` method. EN-1 therefore requires the exact `name` parameter, which is on line 289
of the multiline signature:

```python
def save(
    self,
    storage: FileStorage,
    folder: str | None = None,
    name: str | None = None
) -> str:
```

The strict resolver accepts only whole source lines. Mechanically resolving either the line
`name: str | None = None` or the `def save(` line yields the same Python `FunctionDef` identity in
each revision, not an `arg`:

| revision | node type | structural path | digest |
|---|---|---|---|
| vuln | `FunctionDef` | `(24, 8)` | `be4c0f47...` |
| fixed | `FunctionDef` | `(24, 8)` | `ab28edcb...` |

The digest changes because the inserted behavior changes the function body, which further confirms
that the identity is the whole function. Anchoring it would violate the mandatory self-review rule
requiring the specific parameter, not the containing function.

Later source statements are not valid entry substitutes:

- `name = secure_filename(name)` resolves to an `Assign`, but is a transform after parameter entry;
- `basename = name` resolves to an `Assign`, but is a later local copy;
- both are excluded by EN-3.

No exact statement/parameter entry can therefore be authored under the frozen harness.

## Behavior is not the blocker

The fix adds the statement-level transform `basename = lowercase_ext(basename)` at fixed line 343
(`Assign`, path `(24, 8, 9, 4)`). For the triggering mixed-case override, this is the sole changed
transform and directly determines that the following extension allow-check rejects `php`, so BE-1
is determinate. Under AC-2, the vulnerable absent context is the first reader
`ext = extension(basename)` at vulnerable line 344 (`Assign`, path `(24, 8, 9, 4)`). Both resolve
uniquely. The fixture still fails because entry is a required core item.

## Disposition (§15.2 exhaustion)

- No bundle was built and no judge was run; author truth was never exposed.
- The frozen selection queue and append-only selection log remain unchanged.
- Both Python reserves have now been consumed: Mnemosyne is admissible; Flask-Reuploaded is not.
- The Python tranche target shrinks from N=4 to at most N=3, with no backfill, re-screening, or
  quota-skipped promotion.
- The remaining original primary, AGiXT (`GHSA-5gfj-64gh-mgmw`), is still evaluated next. If it is
  admissible, Python closes at N=3; if not, Python closes at N=2.
