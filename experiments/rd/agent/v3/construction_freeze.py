"""Validate and freeze the non-measured RD v3 construction inputs."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FREEZE = HERE / "construction-freeze.json"
GO_TOOLCHAIN_VERSION = "go1.26.8"
GO_BIN = ROOT / ".cache" / "toolchains" / GO_TOOLCHAIN_VERSION / "bin"
GO = GO_BIN / "go"
GOFMT = GO_BIN / "gofmt"
TRUTH_DIR = ROOT / "experiments" / "rd" / "truth"
if str(TRUTH_DIR) not in sys.path:
    sys.path.insert(0, str(TRUTH_DIR))

import resolver as frozen_resolver  # noqa: E402

REVISIONS = ("revision_A", "revision_B")
LANGUAGES = ("go", "python")
CELLS = (
    "claim_specific_entry",
    "decision_point",
    "changed_present_both",
    "absent_context",
    "statement_granularity",
)
ELIGIBLE_TARGETS = {
    "python_typed_attribute_dispatch": ("python", "call_typed_attribute"),
    "go_direct_argument_binding": ("go", "argument_binding"),
    "go_callback_argument_binding": ("go", "argument_binding"),
}
FALSE_FAMILIES = {
    "python_typed_attribute_dispatch": {"wrong_receiver_type", "unreachable_override"},
    "go_direct_argument_binding": {"wrong_argument_index", "wrong_callee"},
    "go_callback_argument_binding": {"unreachable_callback", "wrong_parameter_index"},
}
STATEMENT_NODES = {
    "go": {"*ast.AssignStmt", "*ast.ReturnStmt", "*ast.IfStmt"},
    "python": {"Assign", "Return", "If"},
}
BOUND = (
    HERE / "CONSTRUCTION-SPEC.md",
    HERE / "a-development.yaml",
    HERE / "a-heldout-spec.yaml",
    HERE / "provider-development.yaml",
    HERE / "provider-heldout-spec.yaml",
    HERE / "selection-seed-spec.yaml",
    HERE / "construction_freeze.py",
    HERE.parent / "V3-PROTOCOL-DELTA.md",
    HERE.parent / "V3-FINAL-REVIEW.md",
    ROOT / "experiments/rd/definitions.yaml",
    ROOT / "results/rd-vocabulary.json",
)
FORBIDDEN_SOURCE_TOKENS = (
    "GO-2026-6237",
    "GHSA-fq2j-j8hc-8vw8",
    "GHSA-mr3j-p26x-72x4",
    "GHSA-hx8v-g79f-8w5f",
    "GHSA-xcw4-53cc-hv32",
    "SiYuan",
    "Vikunja",
    "LiteLLM",
    "Mnemosyne",
    "user_config",
    "localPath",
    "TaskID",
    "valid_signature",
    "ipPayloadLen",
)


class ConstructionError(RuntimeError):
    pass


def load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ConstructionError(f"{path.name}: expected mapping")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_go_toolchain() -> dict:
    try:
        result = subprocess.run([str(GO), "version"], text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise ConstructionError(f"pinned Go toolchain is missing: {GO}") from exc
    if result.returncode:
        raise ConstructionError(f"pinned Go version check failed: {result.stderr.strip()}")
    fields = result.stdout.split()
    version = fields[2] if len(fields) >= 3 else ""
    if version != GO_TOOLCHAIN_VERSION:
        raise ConstructionError(
            f"Go toolchain drift: expected {GO_TOOLCHAIN_VERSION}, got {version or result.stdout.strip()}"
        )
    if not GOFMT.is_file():
        raise ConstructionError(f"pinned gofmt is missing: {GOFMT}")
    return {"go_version": version, "gofmt": str(GOFMT.relative_to(ROOT))}


def exact_line(source: str, anchor: dict, *, statement: bool) -> None:
    if set(anchor) != {"file", "start_line", "end_line", "expression"}:
        raise ConstructionError(f"bad anchor fields: {anchor}")
    start, end, expression = anchor["start_line"], anchor["end_line"], anchor["expression"]
    if not isinstance(start, int) or start != end or start < 1:
        raise ConstructionError(f"anchor must name one positive line: {anchor}")
    lines = source.splitlines()
    if start > len(lines):
        raise ConstructionError(f"anchor line outside source: {anchor}")
    line = lines[start - 1].strip()
    if statement:
        if line != expression:
            raise ConstructionError(f"statement anchor mismatch: {expression!r} != {line!r}")
    elif line.count(expression) != 1:
        raise ConstructionError(f"endpoint expression must occur once on line: {anchor}; line={line!r}")


def statement_identity(source: str, anchor: dict, *, language: str, revision: str) -> str:
    exact_line(source, anchor, statement=True)
    try:
        identity = frozen_resolver.resolve_identity(
            anchor, language=language, revision=revision, source=source
        )
    except frozen_resolver.ResolverError as exc:
        raise ConstructionError(f"frozen resolver rejected A anchor {anchor}: {exc}") from exc
    node_type = identity[3]
    if node_type not in STATEMENT_NODES[language]:
        raise ConstructionError(
            f"A anchor is not a complete statement: {anchor}; resolved node={node_type}"
        )
    return node_type


def syntax(language: str, source: str, name: str) -> None:
    if language == "python":
        try:
            ast.parse(source, filename=name)
        except SyntaxError as exc:
            raise ConstructionError(f"invalid Python {name}: {exc}") from exc
        return
    try:
        result = subprocess.run([str(GOFMT)], input=source, text=True,
                                capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise ConstructionError(f"pinned gofmt is missing: {GOFMT}") from exc
    if result.returncode:
        raise ConstructionError(f"invalid Go {name}: {result.stderr.strip()}")


def validate_a() -> dict:
    doc = load(HERE / "a-development.yaml")
    if doc.get("schema") != "rd-v3-a-development/v1":
        raise ConstructionError("bad A development schema")
    cases = doc.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ConstructionError("A development must contain exactly 10 cases")
    ids, matrix = set(), {(language, cell): 0 for language in LANGUAGES for cell in CELLS}
    node_types: dict[str, int] = {}
    source_text = []
    for case in cases:
        cid, language, cell = case.get("id"), case.get("language"), case.get("cell")
        if not isinstance(cid, str) or cid in ids:
            raise ConstructionError(f"duplicate/bad A case id: {cid}")
        ids.add(cid)
        if (language, cell) not in matrix:
            raise ConstructionError(f"bad A matrix cell: {language}/{cell}")
        matrix[(language, cell)] += 1
        files = case.get("files")
        if not isinstance(files, dict) or set(files) != set(REVISIONS):
            raise ConstructionError(f"{cid}: files must cover both revisions")
        for revision in REVISIONS:
            revision_files = files[revision]
            if not isinstance(revision_files, dict) or not revision_files:
                raise ConstructionError(f"{cid}/{revision}: no files")
            for name, source in revision_files.items():
                if not isinstance(name, str) or not isinstance(source, str):
                    raise ConstructionError(f"{cid}/{revision}: bad source")
                syntax(language, source, f"{cid}/{revision}/{name}")
                source_text.append(source)
        expected = case.get("expected")
        if not isinstance(expected, dict) or set(expected) != {"entry", "behavior"}:
            raise ConstructionError(f"{cid}: expected must contain entry and behavior")
        for kind in ("entry", "behavior"):
            slot = expected[kind]
            if not isinstance(slot, dict) or set(slot) != set(REVISIONS):
                raise ConstructionError(f"{cid}/{kind}: incomplete slot")
            states = []
            for revision in REVISIONS:
                realization = slot[revision]
                state = realization.get("state") if isinstance(realization, dict) else None
                states.append(state)
                key = "anchor" if state == "present" else "context" if state == "absent" else None
                if key is None or set(realization) != {"state", key}:
                    raise ConstructionError(f"{cid}/{kind}/{revision}: bad realization")
                anchor = realization[key]
                source = files[revision].get(anchor.get("file"))
                if source is None:
                    raise ConstructionError(f"{cid}/{kind}/{revision}: unknown file")
                node_type = statement_identity(
                    source, anchor, language=language, revision=revision
                )
                node_types[node_type] = node_types.get(node_type, 0) + 1
            if states == ["absent", "absent"]:
                raise ConstructionError(f"{cid}/{kind}: absent in both revisions")
    if any(count != 1 for count in matrix.values()):
        raise ConstructionError(f"A development matrix must be exactly one per cell: {matrix}")
    joined = "\n".join(source_text + [str(c.get("effect_claim", "")) for c in cases])
    leaked = [token for token in FORBIDDEN_SOURCE_TOKENS if token in joined]
    if leaked:
        raise ConstructionError(f"A development contains v2 tokens: {leaked}")
    return {"cases": len(cases), "matrix": {f"{a}/{b}": n for (a, b), n in matrix.items()},
            "resolved_statement_nodes": dict(sorted(node_types.items()))}


def validate_a_heldout() -> dict:
    doc = load(HERE / "a-heldout-spec.yaml")
    if doc.get("schema") != "rd-v3-a-heldout-spec/v1" or doc.get("instances") != 20:
        raise ConstructionError("bad A held-out header/count")
    if doc.get("languages") != list(LANGUAGES) or doc.get("cases_per_language_cell") != 2:
        raise ConstructionError("bad A held-out language/cell allocation")
    if set(doc.get("cells") or {}) != set(CELLS):
        raise ConstructionError("bad A held-out cells")
    gate = doc.get("gate") or {}
    expected = {"exact_entry_and_behavior_minimum": 16,
                "per_language_cell_minimum": 1,
                "forbidden_granularity_errors_maximum": 0,
                "changed_present_encoded_absent_maximum": 0,
                "harness_invariant_failures_maximum": 0}
    if gate != expected:
        raise ConstructionError(f"A held-out gate drift: {gate}")
    return {"instances": 20, "cells": len(CELLS)}


def validate_provider() -> dict:
    doc = load(HERE / "provider-development.yaml")
    if doc.get("schema") != "rd-v3-provider-development/v1":
        raise ConstructionError("bad provider development schema")
    cases = doc.get("cases")
    if not isinstance(cases, list) or len(cases) != len(ELIGIBLE_TARGETS):
        raise ConstructionError("provider development needs one case per eligible target")
    seen, source_text = set(), []
    for case in cases:
        target = case.get("target")
        if target in seen or target not in ELIGIBLE_TARGETS:
            raise ConstructionError(f"bad/duplicate provider target: {target}")
        seen.add(target)
        language, relation = ELIGIBLE_TARGETS[target]
        if (case.get("language"), case.get("relation")) != (language, relation):
            raise ConstructionError(f"provider target mapping drift: {target}")
        files = case.get("files")
        if not isinstance(files, dict) or not files:
            raise ConstructionError(f"{target}: no provider source")
        for name, source in files.items():
            syntax(language, source, f"{target}/{name}")
            source_text.append(source)
        edges = case.get("edges")
        if not isinstance(edges, list) or sum(e.get("truth") is True for e in edges) != 2 \
                or sum(e.get("truth") is False for e in edges) != 2:
            raise ConstructionError(f"{target}: provider dev requires 2 true and 2 false")
        if len({e.get("id") for e in edges}) != len(edges):
            raise ConstructionError(f"{target}: duplicate edge id")
        false_families = [e.get("false_family") for e in edges if e.get("truth") is False]
        if len(false_families) != len(set(false_families)) \
                or set(false_families) != FALSE_FAMILIES[target]:
            raise ConstructionError(f"{target}: false-family coverage drift: {false_families}")
        for edge in edges:
            if edge.get("truth") is False and not edge.get("false_family"):
                raise ConstructionError(f"{target}/{edge.get('id')}: false edge needs family")
            for side in ("from", "to"):
                anchor = edge.get(side)
                source = files.get(anchor.get("file")) if isinstance(anchor, dict) else None
                if source is None:
                    raise ConstructionError(f"{target}/{edge.get('id')}: unknown endpoint file")
                exact_line(source, anchor, statement=False)
    if seen != set(ELIGIBLE_TARGETS):
        raise ConstructionError("provider development target coverage mismatch")
    joined = "\n".join(source_text)
    leaked = [token for token in FORBIDDEN_SOURCE_TOKENS if token in joined]
    if leaked:
        raise ConstructionError(f"provider development contains v2 tokens: {leaked}")
    return {"targets": len(seen), "true_edges": 2 * len(seen), "false_edges": 2 * len(seen)}


def validate_provider_heldout() -> dict:
    doc = load(HERE / "provider-heldout-spec.yaml")
    if doc.get("schema") != "rd-v3-provider-heldout-spec/v1":
        raise ConstructionError("bad provider held-out schema")
    rows = doc.get("eligible_targets")
    if not isinstance(rows, list) or len(rows) != len(ELIGIBLE_TARGETS):
        raise ConstructionError("provider held-out needs one row per eligible target")
    found = {}
    for row in rows or []:
        target = row.get("id")
        if target in found:
            raise ConstructionError(f"duplicate provider held-out target: {target}")
        if set(row.get("false_families") or []) != FALSE_FAMILIES.get(target, set()):
            raise ConstructionError(f"provider held-out false-family drift: {target}")
        found[target] = (row.get("language"), row.get("relation"),
                         row.get("true_cases"), row.get("false_cases"))
    expected = {name: (*mapping, 2, 2) for name, mapping in ELIGIBLE_TARGETS.items()}
    if found != expected:
        raise ConstructionError(f"provider held-out allocation drift: {found}")
    ineligible = {row.get("id") for row in doc.get("ineligible_targets") or []}
    if ineligible != {"scalar_to_guard", "lexical_control_dependency",
                      "generic_same_object_expansion"}:
        raise ConstructionError(f"provider ineligible-target drift: {sorted(ineligible)}")
    if (doc.get("gate") or {}).get("false_verified_maximum") != 0:
        raise ConstructionError("provider unsafe gate drift")
    return {"targets": len(found), "instances": sum(row[2] + row[3] for row in found.values())}


def validate_selection() -> dict:
    doc = load(HERE / "selection-seed-spec.yaml")
    if doc.get("schema") != "rd-v3-selection-seed-spec/v1":
        raise ConstructionError("bad selection seed schema")
    if doc.get("target") != {"go": 3, "python": 3} or doc.get("reserves") != {"go": 3, "python": 3}:
        raise ConstructionError("selection target/reserve drift")
    nonce = doc.get("nonce") or {}
    if nonce.get("bytes") != 32 or nonce.get("retries") != 0 \
            or nonce.get("reveal") != "after_treatment_freeze_and_synthetic_gate_pass":
        raise ConstructionError("selection nonce procedure drift")
    derivation = doc.get("derivation") or {}
    if derivation.get("algorithm") != "sha256" or derivation.get("integer") != "unsigned_big_endian":
        raise ConstructionError("selection derivation drift")
    return {"target": 6, "reserves": 6, "nonce_bytes": 32}


def validation() -> dict:
    missing = [str(path.relative_to(ROOT)) for path in BOUND if not path.exists()]
    if missing:
        raise ConstructionError(f"missing bound files: {missing}")
    return {"toolchain": validate_go_toolchain(),
            "a_development": validate_a(), "a_heldout": validate_a_heldout(),
            "provider_development": validate_provider(),
            "provider_heldout": validate_provider_heldout(), "selection": validate_selection()}


def clean_tracked_tree() -> None:
    result = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
                            text=True, capture_output=True, check=True)
    if result.stdout.strip():
        raise ConstructionError("tracked tree must be clean before construction freeze write")


def build() -> dict:
    clean_tracked_tree()
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True,
                            capture_output=True, check=True).stdout.strip()
    checks = validation()
    return {"schema": "rd-v3-construction-freeze/v1", "protocol": "rd-v3",
            "created_from_commit": commit,
            "files": {str(path.relative_to(ROOT)): sha256(path) for path in BOUND},
            "validation": checks}


def write() -> None:
    if FREEZE.exists():
        raise ConstructionError("construction freeze already exists; do not overwrite")
    doc = build()
    FREEZE.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "WROTE", "commit": doc["created_from_commit"],
                      "files": len(doc["files"]), "validation": doc["validation"]}, indent=2))


def verify() -> dict:
    if not FREEZE.exists():
        raise ConstructionError("construction freeze is missing")
    frozen = json.loads(FREEZE.read_text())
    problems = []
    for name, expected in (frozen.get("files") or {}).items():
        path = ROOT / name
        if not path.exists() or sha256(path) != expected:
            problems.append(f"file drift: {name}")
    try:
        checks = validation()
        if checks != frozen.get("validation"):
            problems.append("validation summary drift")
    except ConstructionError as exc:
        problems.append(str(exc))
    if problems:
        raise ConstructionError("; ".join(problems))
    return frozen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write", "verify"))
    args = parser.parse_args()
    if args.command == "check":
        print(json.dumps({"status": "OK", "validation": validation()}, indent=2))
    elif args.command == "write":
        write()
    else:
        doc = verify()
        print(json.dumps({"status": "OK", "protocol": doc["protocol"],
                          "created_from_commit": doc["created_from_commit"]}, indent=2))


if __name__ == "__main__":
    main()
