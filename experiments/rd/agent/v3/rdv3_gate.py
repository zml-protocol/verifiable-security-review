"""Validate, prepare, execute, and score the one-shot RD v3 synthetic gate.

The held-out commitment is authored outside the repository after treatment
freeze.  This tool validates and materializes it without changing the frozen
matrix, then scores A artifacts and deterministic provider edges mechanically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
TRUTH_TOOLS = ROOT / "experiments" / "rd" / "truth"
for directory in (HERE, PARENT, TRUTH_TOOLS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import resolver  # noqa: E402

import construction_freeze_v2 as construction  # noqa: E402
import rdv3_contract as contract  # noqa: E402
import rdv3_freeze as treatment_freeze  # noqa: E402
import rdv3_provider_dev as provider  # noqa: E402
import rdv3_runner as runner  # noqa: E402
import rdv3_score as scorer  # noqa: E402

CELLS = tuple(construction.v1.CELLS)
LANGUAGES = tuple(construction.v1.LANGUAGES)
LURE_FAMILIES = frozenset({
    "upstream_container", "field_declaration", "later_derivative", "computed_value",
    "sink_argument", "wrong_context", "nonexistent_present", "nearby_statement",
    "subexpression", "enclosing_function",
})
STRUCTURAL_FORBIDDEN = frozenset({"subexpression", "field_declaration", "enclosing_function"})
HELDOUT = ROOT / "experiments" / "rd" / "agent" / "v3" / "heldout"
RUN_ROOT = runner.RUNS / "heldout_a"
PREPARED = runner.RUNS / "heldout-prepared"
PROVIDER_RUN = runner.RUNS / "heldout-provider"
GATE_RESULT = runner.RUNS / "heldout-gate-result.json"


class GateError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(files: dict[str, str]) -> str:
    return hashlib.sha256(contract.canonical_bytes(sorted(files.items()))).hexdigest()


def _safe_relative(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise GateError(f"held-out path must be relative and contained: {name!r}")
    return path


def commitment(path: Path) -> tuple[dict, dict[str, dict], dict[str, dict]]:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise GateError("held-out commitment must be materialized inside the repository")
    doc = json.loads(path.read_text())
    if doc.get("schema") != "rd-v3-heldout-commitment/v1":
        raise GateError("bad held-out commitment schema")
    if sha256(treatment_freeze.FREEZE) != doc.get("treatment_freeze_sha256"):
        raise GateError("held-out commitment names another treatment freeze")
    if sha256(HERE / "construction-freeze-v2.json") != doc.get("construction_freeze_sha256"):
        raise GateError("held-out commitment names another construction freeze")
    curator = doc.get("curator") or {}
    if curator.get("role") != "non_implementing_curator" \
            or curator.get("independence_attestation") is not True:
        raise GateError("held-out commitment lacks curator independence attestation")
    files = doc.get("files")
    if not isinstance(files, dict) or not files:
        raise GateError("held-out commitment has no file hash map")
    actual = {}
    for name, expected in files.items():
        relative = _safe_relative(name)
        target = path.parent / relative
        if not target.is_file():
            raise GateError(f"missing committed held-out file: {name}")
        actual[name] = sha256(target)
        if actual[name] != expected:
            raise GateError(f"held-out file hash drift: {name}")
    if actual != files or aggregate(files) != doc.get("aggregate_sha256"):
        raise GateError("held-out aggregate hash drift")
    listed = set(doc.get("a_cases") or []) | set(doc.get("provider_cases") or [])
    if listed != set(files):
        raise GateError("every committed held-out file must be exactly one listed case")
    tracked = [path, *(path.parent / _safe_relative(name) for name in files)]
    for target in tracked:
        relative = str(target.resolve().relative_to(ROOT))
        check = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", relative],
                               capture_output=True, check=False)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", relative],
                               capture_output=True, text=True, check=True).stdout.strip()
        if check.returncode or dirty:
            raise GateError(f"held-out commitment must be tracked and clean: {relative}")
    a_cases = {name: yaml.safe_load((path.parent / _safe_relative(name)).read_text())
               for name in doc.get("a_cases") or []}
    provider_cases = {name: yaml.safe_load((path.parent / _safe_relative(name)).read_text())
                      for name in doc.get("provider_cases") or []}
    validate_a_cases(list(a_cases.values()))
    validate_provider_cases(list(provider_cases.values()))
    return doc, a_cases, provider_cases


def validate_a_cases(cases: list[dict]) -> None:
    if len(cases) != 20:
        raise GateError("A held-out commitment must contain exactly 20 cases")
    ids, matrix = set(), {(language, cell): 0 for language in LANGUAGES for cell in CELLS}
    all_source = []
    development = yaml.safe_load((HERE / "a-development.yaml").read_text())["cases"]
    development_effects = {case["effect_claim"] for case in development}
    development_source_hashes = {
        hashlib.sha256(source.encode()).hexdigest()
        for case in development for files in case["files"].values() for source in files.values()
    }
    for case in cases:
        if case.get("schema") != "rd-v3-a-heldout-case/v1":
            raise GateError("bad A held-out case schema")
        task_id, language, cell = case.get("task_id"), case.get("language"), case.get("cell")
        if not isinstance(task_id, str) or not task_id or task_id in ids:
            raise GateError(f"bad or duplicate held-out task id: {task_id}")
        ids.add(task_id)
        if (language, cell) not in matrix:
            raise GateError(f"unknown held-out matrix cell: {language}/{cell}")
        matrix[(language, cell)] += 1
        if not isinstance(case.get("package"), str) or not case["package"].strip() \
                or not isinstance(case.get("effect_claim"), str) or not case["effect_claim"].strip():
            raise GateError(f"{task_id}: package/effect claim must be strings")
        if case["effect_claim"] in development_effects:
            raise GateError(f"{task_id}: effect claim duplicates development")
        files = case.get("files")
        if not isinstance(files, dict) or set(files) != set(contract.REVISIONS):
            raise GateError(f"{task_id}: files must cover revision_A and revision_B")
        for revision, revision_files in files.items():
            if not isinstance(revision_files, dict) or not revision_files:
                raise GateError(f"{task_id}/{revision}: no source files")
            for name, source in revision_files.items():
                construction.v1.syntax(language, source, f"{task_id}/{revision}/{name}")
                if hashlib.sha256(source.encode()).hexdigest() in development_source_hashes:
                    raise GateError(f"{task_id}: source duplicates development")
                all_source.append(source)
        expected = case.get("expected")
        if not isinstance(expected, dict) or set(expected) != {"entry", "behavior"}:
            raise GateError(f"{task_id}: expected must contain entry and behavior")
        for kind, slot in expected.items():
            if not isinstance(slot, dict) or set(slot) != set(contract.REVISIONS):
                raise GateError(f"{task_id}/{kind}: incomplete expected slot")
            for revision, realization in slot.items():
                state = realization.get("state") if isinstance(realization, dict) else None
                key = "anchor" if state == "present" else "context" if state == "absent" else None
                if key is None or set(realization) != {"state", key}:
                    raise GateError(f"{task_id}/{kind}/{revision}: bad realization")
                anchor = realization[key]
                source = files[revision].get(anchor.get("file"))
                if source is None:
                    raise GateError(f"{task_id}/{kind}/{revision}: anchor names unknown file")
                construction.v1.statement_identity(
                    source, anchor, language=language, revision=revision)
        lure_families = case.get("lure_families")
        if not isinstance(lure_families, list) or not lure_families \
                or any(family not in LURE_FAMILIES for family in lure_families):
            raise GateError(f"{task_id}: at least one known lure family is required")
        forbidden = case.get("forbidden_anchors") or []
        if not isinstance(forbidden, list):
            raise GateError(f"{task_id}: forbidden_anchors must be a list")
        if cell == "statement_granularity" and not forbidden:
            raise GateError(f"{task_id}: statement-granularity case needs a structural lure anchor")
        for lure in forbidden:
            if lure.get("family") not in STRUCTURAL_FORBIDDEN:
                raise GateError(f"{task_id}: unknown forbidden-anchor family")
            if lure.get("kind") not in ("entry", "behavior") \
                    or lure.get("revision") not in contract.REVISIONS:
                raise GateError(f"{task_id}: malformed forbidden anchor")
            anchor = lure.get("anchor") or {}
            source = files[lure["revision"]].get(anchor.get("file"))
            if source is None:
                raise GateError(f"{task_id}: forbidden anchor names unknown file")
            construction.v1.exact_line(source, anchor, statement=False)
        if cell == "changed_present_both":
            changed = case.get("changed_slot")
            if changed not in ("entry", "behavior") \
                    or any(expected[changed][revision]["state"] != "present"
                           for revision in contract.REVISIONS):
                raise GateError(f"{task_id}: changed-present case needs a present/present changed_slot")
        elif case.get("changed_slot") is not None:
            raise GateError(f"{task_id}: only changed-present cases may name changed_slot")
    if any(count != 2 for count in matrix.values()):
        raise GateError(f"A held-out matrix drift: {matrix}")
    joined = "\n".join(all_source + [str(case.get("effect_claim")) for case in cases])
    leaked = [token for token in construction.v1.FORBIDDEN_SOURCE_TOKENS if token in joined]
    if leaked or "CWE-" in joined or "GHSA-" in joined:
        raise GateError(f"held-out A source/claims contain forbidden identifiers: {leaked}")


def validate_provider_cases(cases: list[dict]) -> None:
    if len(cases) != 3:
        raise GateError("provider held-out commitment must contain three target cases")
    seen = set()
    development = yaml.safe_load((HERE / "provider-development-v2.yaml").read_text())["cases"]
    development_source_hashes = {
        hashlib.sha256(source.encode()).hexdigest()
        for case in development for source in case["files"].values()
    }
    for case in cases:
        if case.get("schema") != "rd-v3-provider-heldout-case/v1":
            raise GateError("bad provider held-out case schema")
        target = case.get("target")
        if target in seen or target not in construction.v1.ELIGIBLE_TARGETS:
            raise GateError(f"bad or duplicate provider target: {target}")
        seen.add(target)
        language, relation = construction.v1.ELIGIBLE_TARGETS[target]
        if (case.get("language"), case.get("relation")) != (language, relation):
            raise GateError(f"provider target mapping drift: {target}")
        edges = case.get("edges") or []
        if len(edges) != 4 or sum(edge.get("truth") is True for edge in edges) != 2 \
                or sum(edge.get("truth") is False for edge in edges) != 2:
            raise GateError(f"{target}: provider challenge needs two true and two false")
        families = {edge.get("false_family") for edge in edges if edge.get("truth") is False}
        if families != construction.v1.FALSE_FAMILIES[target]:
            raise GateError(f"{target}: false-family drift")
        files = case.get("files") or {}
        for name, source in files.items():
            construction.v1.syntax(language, source, f"{target}/{name}")
            if hashlib.sha256(source.encode()).hexdigest() in development_source_hashes:
                raise GateError(f"{target}: source duplicates development")
        for edge in edges:
            for side in ("from", "to"):
                anchor = edge.get(side) or {}
                source = files.get(anchor.get("file"))
                if source is None:
                    raise GateError(f"{target}/{edge.get('id')}: unknown endpoint file")
                construction.v1.exact_line(source, anchor, statement=False)
            if target == "python_typed_attribute_dispatch":
                construction.nested_attribute_call(files[edge["from"]["file"]], edge["from"])
                construction.inside_python_function(files[edge["to"]["file"]], edge["to"])
    if seen != set(construction.v1.ELIGIBLE_TARGETS):
        raise GateError("provider held-out target set is incomplete")
    joined = "\n".join(case_source for case in cases for case_source in case["files"].values())
    leaked = [token for token in construction.v1.FORBIDDEN_SOURCE_TOKENS if token in joined]
    if leaked:
        raise GateError(f"provider held-out source contains forbidden identifiers: {leaked}")


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            env=env, check=False)
    if result.returncode:
        raise GateError(result.stderr.strip())
    return result.stdout.strip()


def _replace_files(repo: Path, files: dict[str, str]) -> None:
    for old in repo.iterdir():
        if old.name != ".git":
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
    for name, source in files.items():
        path = repo / _safe_relative(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def prepare_a(commitment_path: Path, authorization_usd: float) -> Path:
    doc, case_map, _ = commitment(commitment_path)
    if authorization_usd < 60.0:
        raise GateError("HELDOUT_NOT_STARTED_BUDGET_AUTHORIZATION")
    if PREPARED.exists():
        raise GateError("held-out prepared directory already exists; do not regenerate")
    tasks = []
    env = {**os.environ, "GIT_AUTHOR_NAME": "RD V3 Heldout",
           "GIT_AUTHOR_EMAIL": "rd-v3-heldout@example.invalid",
           "GIT_COMMITTER_NAME": "RD V3 Heldout",
           "GIT_COMMITTER_EMAIL": "rd-v3-heldout@example.invalid",
           "GIT_AUTHOR_DATE": "2026-10-03T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-10-03T00:00:00Z"}
    for name in doc["a_cases"]:
        case = case_map[name]
        repo = PREPARED / "repos" / case["task_id"]
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        _replace_files(repo, case["files"]["revision_A"])
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "held-out revision A", env=env)
        first = _git(repo, "rev-parse", "HEAD")
        _replace_files(repo, case["files"]["revision_B"])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "held-out revision B", env=env)
        second = _git(repo, "rev-parse", "HEAD")
        tasks.append({"task_id": case["task_id"], "task_kind": "synthetic_a",
                      "fixture": case["task_id"], "language": case["language"],
                      "package": case["package"], "effect_claim": case["effect_claim"],
                      "repo": str(repo), "revisions": {"revision_A": first, "revision_B": second},
                      "heldout_case_path": str((commitment_path.parent / name).resolve())})
    manifest = {"schema": "rd-v3-run-manifest/v1", "protocol": "rd-v3", "mode": "heldout_a",
                "tasks": tasks, "launch_ceiling_usd": 60.0,
                "user_authorization_usd": authorization_usd,
                "treatment_freeze_sha256": sha256(treatment_freeze.FREEZE),
                "heldout_commitment_sha256": sha256(commitment_path)}
    PREPARED.mkdir(parents=True, exist_ok=True)
    path = PREPARED / "run-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    runner.load_manifest(path)
    return path


def _resolved_slot(task: dict, slot: dict) -> dict:
    source = Source(task)
    return resolver.resolve_doc({"items": [{"id": "slot", "kind": "entry", "entry": slot}]},
                                language=task["language"], source_provider=source.text)["items"][0]["entry"]


class Source:
    def __init__(self, task: dict):
        from source import SourceSurface
        self.surface = SourceSurface(task["repo"], task["revisions"])

    def text(self, revision: str, file: str) -> str:
        return self.surface.text(revision, file)


def _slot_identity(task: dict, kind: str, slot: dict) -> tuple:
    source = Source(task)
    item = resolver.resolve_doc(
        {"items": [{"id": kind, "kind": kind, kind: slot}]},
        language=task["language"], source_provider=source.text)["items"][0]
    return scorer.agreement.item_identity(item, scorer._identity)


def _attempt(task_id: str) -> Path | None:
    return scorer._terminal_attempt(RUN_ROOT, task_id)


def score_a_gate(commitment_path: Path, run_manifest_path: Path) -> dict:
    commitment_doc, case_map, _ = commitment(commitment_path)
    manifest = runner.load_manifest(run_manifest_path)
    if manifest["mode"] != "heldout_a" or manifest.get("heldout_commitment_sha256") != sha256(commitment_path):
        raise GateError("held-out run manifest does not bind the commitment")
    treatment = treatment_freeze.verify()
    by_id = {case["task_id"]: case for case in case_map.values()}
    rows, harness = [], {}
    for task in manifest["tasks"]:
        case = by_id.get(task["task_id"])
        if case is None:
            raise GateError(f"run task has no committed case: {task['task_id']}")
        attempt = _attempt(task["task_id"])
        a = None
        if attempt:
            problems = scorer.harness_problems(task, attempt, treatment)
            record = json.loads((attempt / "attempt.json").read_text())
            if record.get("status") in ("INFRA_INVALID", "HARNESS_INVALID", "BUDGET_CENSORED"):
                problems.append(f"non-measurement terminal status: {record.get('status')}")
            if problems:
                harness[task["task_id"]] = problems
            a_path = attempt / "artifacts" / "a.json"
            if a_path.exists():
                a = json.loads(a_path.read_text())
                contract.verify_seal(a)
        else:
            harness[task["task_id"]] = ["held-out task has no terminal attempt"]
        exact_entry = exact_behavior = False
        forbidden_errors = []
        changed_absent = False
        if a:
            requirements = a["requirements"]
            exact_entry = (_slot_identity(task, "entry", requirements["entry"]) ==
                           _slot_identity(task, "entry", case["expected"]["entry"]))
            exact_behavior = (_slot_identity(task, "behavior", requirements["behavior"]) ==
                              _slot_identity(task, "behavior", case["expected"]["behavior"]))
            source = Source(task)
            for lure in case["forbidden_anchors"]:
                revision, kind = lure["revision"], lure["kind"]
                realization = requirements[kind][revision]
                if realization["state"] != "present":
                    continue
                try:
                    got = resolver.resolve_identity(realization["anchor"], language=task["language"],
                                                    revision=revision,
                                                    source=source.text(revision, realization["anchor"]["file"]))
                    bad = resolver.resolve_identity(lure["anchor"], language=task["language"],
                                                    revision=revision,
                                                    source=source.text(revision, lure["anchor"]["file"]))
                    if got == bad:
                        forbidden_errors.append(lure["family"])
                except Exception:
                    pass
            changed = case.get("changed_slot")
            changed_absent = bool(changed and any(
                requirements[changed][revision]["state"] == "absent"
                for revision in contract.REVISIONS))
        rows.append({"task_id": task["task_id"], "language": case["language"],
                     "cell": case["cell"], "a_locked": a is not None,
                     "entry_exact": exact_entry, "behavior_exact": exact_behavior,
                     "case_exact": exact_entry and exact_behavior,
                     "forbidden_anchor_errors": forbidden_errors,
                     "changed_present_encoded_absent": changed_absent})
    exact = sum(row["case_exact"] for row in rows)
    cells = {f"{language}/{cell}": sum(row["case_exact"] and row["language"] == language
                                       and row["cell"] == cell for row in rows)
             for language in LANGUAGES for cell in CELLS}
    forbidden = sum(len(row["forbidden_anchor_errors"]) for row in rows)
    changed = sum(row["changed_present_encoded_absent"] for row in rows)
    passed = exact >= 16 and all(value >= 1 for value in cells.values()) \
        and forbidden == 0 and changed == 0 and not harness
    return {"schema": "rd-v3-a-heldout-result/v1",
            "status": ("PASS" if passed else
                       "CALIBRATION_INVALID" if harness else "A_CALIBRATION_FAILED"),
            "commitment_sha256": sha256(commitment_path), "cases_exact": exact,
            "cases_total": len(rows), "cell_exact": cells,
            "forbidden_anchor_errors": forbidden,
            "changed_present_encoded_absent": changed,
            "harness_invariant_failures": harness, "cases": rows}


def run_provider_gate(commitment_path: Path) -> dict:
    doc, _, case_map = commitment(commitment_path)
    attempts = sorted(PROVIDER_RUN.glob("attempt-*")) if PROVIDER_RUN.exists() else []
    if attempts:
        prior = json.loads((attempts[-1] / "attempt.json").read_text())
        if prior.get("status") != "INCONCLUSIVE_TOOL_FAILURE":
            raise GateError("provider held-out gate already has a valid terminal attempt")
    if len(attempts) >= 2:
        raise GateError("provider held-out infrastructure retry is exhausted")
    attempt = PROVIDER_RUN / f"attempt-{len(attempts) + 1}"
    attempt.mkdir(parents=True)
    rows = []
    try:
        for name in doc["provider_cases"]:
            case = dict(case_map[name])
            case.pop("schema", None)
            rows.append(provider.one(case, force=False, out=attempt))
    except Exception as exc:
        record = {"status": "INCONCLUSIVE_TOOL_FAILURE", "error_type": type(exc).__name__,
                  "completed_targets": [row["target"] for row in rows]}
        (attempt / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
        raise GateError(f"provider tool failure; one infrastructure-only retry may apply: {exc}") from exc
    unsafe = any(row["disposition"] == "UNSAFE_PROVIDER" for row in rows)
    status = "UNSAFE_PROVIDER" if unsafe else "PASS"
    record = {"status": status, "completed_targets": [row["target"] for row in rows]}
    (attempt / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
    result = {"schema": "rd-v3-provider-heldout-result/v1", "status": status,
              "commitment_sha256": sha256(commitment_path), "targets": rows,
              "unsafe": unsafe, "attempt": attempt.name}
    (PROVIDER_RUN / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def combine(a_result_path: Path, provider_result_path: Path) -> dict:
    a = json.loads(a_result_path.read_text())
    p = json.loads(provider_result_path.read_text())
    if a.get("commitment_sha256") != p.get("commitment_sha256"):
        raise GateError("A/provider results do not share a held-out commitment")
    if p.get("status") == "UNSAFE_PROVIDER":
        status = "UNSAFE_PROVIDER"
    elif a.get("status") == "CALIBRATION_INVALID" or p.get("status") != "PASS" \
            or a.get("harness_invariant_failures"):
        status = "CALIBRATION_INVALID"
    elif a.get("status") != "PASS":
        status = "A_CALIBRATION_FAILED"
    else:
        status = "PASS"
    result = {"schema": "rd-v3-synthetic-gate-result/v1", "status": status,
              "commitment_sha256": a["commitment_sha256"], "a": a, "provider": p}
    GATE_RESULT.parent.mkdir(parents=True, exist_ok=True)
    GATE_RESULT.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("commitment", type=Path)
    prepare = sub.add_parser("prepare-a")
    prepare.add_argument("commitment", type=Path)
    prepare.add_argument("--authorization-usd", type=float, required=True)
    score = sub.add_parser("score-a")
    score.add_argument("commitment", type=Path)
    score.add_argument("manifest", type=Path)
    score.add_argument("--out", type=Path, required=True)
    provider_parser = sub.add_parser("run-provider")
    provider_parser.add_argument("commitment", type=Path)
    combined = sub.add_parser("combine")
    combined.add_argument("a_result", type=Path)
    combined.add_argument("provider_result", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        doc, a_cases, provider_cases = commitment(args.commitment)
        result = {"status": "OK", "aggregate_sha256": doc["aggregate_sha256"],
                  "a_cases": len(a_cases), "provider_cases": len(provider_cases)}
    elif args.command == "prepare-a":
        result = {"manifest": str(prepare_a(args.commitment, args.authorization_usd))}
    elif args.command == "score-a":
        result = score_a_gate(args.commitment, args.manifest)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    elif args.command == "run-provider":
        result = run_provider_gate(args.commitment)
    else:
        result = combine(args.a_result, args.provider_result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
