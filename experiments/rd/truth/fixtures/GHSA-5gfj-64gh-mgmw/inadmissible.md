# AGiXT (GHSA-5gfj-64gh-mgmw) — INADMISSIBLE (entry INDETERMINATE_TRUTH); Python tranche closed

Final Python primary (original primary #4). **Not frozen as an admissible fixture truth.** The
executable path-traversal flip and exact behavior anchor are established, but no exact source-level
entry for the attacker-controlled path can be expressed under the frozen whole-line
resolver/matcher. Python reserves were already exhausted, so this result closes the Python tranche
at N=2.

## Executable truth remains established

The identical offline probe called `essential_abilities.safe_join()` with a fake instance whose
`WORKING_DIRECTORY` was a fresh temporary directory:

- control `inside/probe.txt`: both revisions returned a path inside the workspace;
- traversal `../<base>-escape/probe.txt` at vuln
  (`872f519fcc75eb574d717ea10ca91fc089718ffe`): returned an outside sibling path and created the
  outside directory;
- the same traversal at fixed (`2079ea5a88fa671a921bf0b5eba887a5a1b73d5f`): raised
  `PermissionError: Path traversal detected: refusing to access path outside workspace` and did not
  create the outside directory.

The advisory independently states that authenticated command callers can supply traversal
filenames to read, write, or delete host files. The flip is real; the inadmissibility concerns only
§15.3 requirement anchoring.

## Why entry truth is not expressible

For the advisory-backed endpoint scenario, the attacker controls the authenticated command request,
including `command_args.filename`. The natural EN-1/EN-2 candidates all fail the mandatory exact
statement/parameter self-review:

| candidate | frozen resolver result | reason it cannot be the entry |
|---|---|---|
| `command: CommandExecution,` in `run_command_v1` (`agixt/endpoints/Extension.py:151`) | `AsyncFunctionDef` | whole route function, not the request parameter |
| `command_args=command.command_args,` in the endpoint call (line 166) | `Call` | the entire multiline `execute_command` call, not a definition extracting `command_args` |
| `command_args: Dict[str, Any] = {}` (`agixt/Models.py:763`) | `AnnAssign` | Pydantic field schema/default, not the runtime request-field extraction |
| `filename: str,` in `read_file` (vuln line 491 / fixed 502) | `AsyncFunctionDef` | whole command method, not the filename parameter |
| `def safe_join(self, paths) -> str:` (line 424) | `FunctionDef` | whole helper, not its `paths` parameter |

The advisory describes its source as `command_args = command.command_args`, but at these canonical
revisions that text is the keyword line inside a larger call, not an assignment statement. The
matcher result confirms that distinction. Later assignments and uses are derived after the request
or command parameter and are excluded by EN-3. Anchoring a containing call/function merely because
it contains the desired value would repeat the coarse-anchor errors the self-review was introduced
to prevent.

There is therefore no valid entry item to author in `requirement-truth.yaml`.

## Behavior is not the blocker

The fix makes three ordered path changes inside `safe_join`: it computes a real base, computes a
real candidate path, then adds the containment guard
`if not (new_path.startswith(base + os.sep) or new_path == base):`.

For the stated `../...` triggering input, BE-3 is determinate: the final guard is the changed check
nearest the filesystem effect whose result directly decides whether execution reaches directory
creation and returns the outside path. It resolves uniquely to an `If` at fixed line 446, structural
path `(23, 7, 6)`. Under AC-1, the vulnerable absent context is the first statement after that guard,
`path_dir = os.path.dirname(new_path)` at vulnerable line 439, a unique `Assign` at path
`(23, 7, 5)`. The realpath assignments feed the deciding guard and are not competing behaviors.

## Disposition (§15.2 exhaustion)

- No bundle was built and no judge was run; author truth was never exposed.
- The frozen selection queue and append-only selection log remain unchanged.
- No Python reserve remains. There is no backfill, re-screening, or quota-skipped promotion.
- Python closes at **N=2**: LiteLLM and Mnemosyne.
- Combined with Go's frozen N=3, RD C.4 realizes **N=5 of the planned N=8**.
