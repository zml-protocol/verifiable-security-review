# llama-stack (GHSA-xmfj-7pp5-fxr6) — INADMISSIBLE (entry INDETERMINATE_TRUTH); reserve substituted

Python primary queue position #3. **Not frozen as an admissible fixture truth.** The executable
password-in-log flip is established, and the changed behavior is statement-expressible, but the
fixture has no valid, exactly anchored entry under the frozen claim/EN semantics. Under the frozen
harness rule this is a measurement result, not a reason to change the definitions, matcher, or
resolver.

## Executable truth remains established

The identical offline probe called `PGVectorVectorIOAdapter.initialize()` with a
`PGVectorVectorIOConfig` containing password `rd-probe-pgvector-secret-12345` at both revisions. It
stopped before database access by stubbing `kvstore_impl`:

- vuln (`752a6836a02e5c23303ce6781e7698e35b52eae7`): the initialization log contains the literal
  password;
- fixed (`b709bd77b6c1fad68a30a4888baa6f2337eaef6f`): the same log contains `password: '******'` and
  not the literal password.

This input/result flip is real. The inadmissibility concerns only §15.3 requirement truth.

## Why entry truth is indeterminate

The advisory's sensitive value is a deployment/operator-supplied PGVector password. The threat is
that an observer with log access learns that secret. It is not an attacker-controlled triggering
input: treating the password as attacker-controlled would make the claimed disclosure vacuous,
because that attacker already knows the value. Treating adapter initialization as the attacker input
does not solve this—the initialization trigger is not the password value whose disclosure constitutes
CWE-532.

This conflicts with the frozen claim and entry definitions, which require an attacker-controlled
triggering input and define entry as the first repository point where that input becomes a value.
The exact password assignment is performed by Pydantic-generated model initialization and has no
source statement in this repository. The source-level candidates do not provide a valid substitute:

| candidate | frozen resolver result | reason it cannot be the entry |
|---|---|---|
| `get_adapter_impl(config: ..., deps: ...)` at `pgvector/__init__.py:12` | `AsyncFunctionDef` | whole function, not the exact `config` parameter required by EN-1 |
| `PGVectorVectorIOAdapter.__init__` signature line at `pgvector.py:333` | `FunctionDef` | whole function, not the exact `config` parameter |
| `password: ... = Field(...)` at `config.py:21` | `AnnAssign` | class-field schema/default declaration, not the runtime definition that receives a supplied password |
| `self.config = config` at `pgvector.py:336` | `Assign` | later storage of an already-received config, excluded by EN-3 |
| `env_value = os.environ.get(env_var)` at `core/stack.py:372` | `Assign` | only one optional configuration path and still reads operator-controlled state, not attacker input |

Anchoring either function declaration merely because it contains a parameter would repeat the
coarse-anchor error prohibited by `ANCHOR-SELF-REVIEW.md`. There is therefore no honest entry item
to place in `requirement-truth.yaml`.

## Behavior is not the blocker

The fix adds one statement-level transform,
`safe_config = {**self.config.model_dump(exclude={"password"}), "password": "******"}`
(`Assign`, fixed line 345), and the next statement logs the transformed value. Under BE-1 and AC-2,
the vulnerable absent context would be the line-344 `log.info(...)` call. These nodes resolve
uniquely, and there is no BE-3 branch ambiguity. The fixture is nevertheless inadmissible because a
core entry item is indeterminate.

## Disposition (§15.2 substitution)

- No bundle was built and no judge was run; author truth was never exposed.
- The frozen selection queue and append-only selection log remain unchanged.
- The final Python reserve is promoted: **Flask-Reuploaded (`GHSA-937x-gpqr-72gg`, CWE-178 /
  CWE-434, reserve position #22)**. The per-CWE-class quota remains satisfied.
- Python reserves are now exhausted. If Flask-Reuploaded or the remaining AGiXT primary is
  inadmissible, the Python tranche shrinks; there is no backfill.
- The next work item is Flask-Reuploaded, before returning to AGiXT.
