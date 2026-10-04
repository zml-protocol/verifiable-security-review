"""Validate the bounded RD v3 construction erratum and write its superseding freeze."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FREEZE = HERE / "construction-freeze-v2.json"
PROVIDER = HERE / "provider-development-v2.yaml"
ERRATUM = HERE / "CONSTRUCTION-ERRATUM.md"


def local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v1 = local_module("rd_v3_construction_freeze_v1", HERE / "construction_freeze.py")

BOUND = tuple(dict.fromkeys((*v1.BOUND, v1.FREEZE, ERRATUM, PROVIDER, Path(__file__).resolve())))


class ConstructionV2Error(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ConstructionV2Error(f"{path.name}: expected mapping")
    return value


def nested_attribute_call(source: str, anchor: dict) -> None:
    """Require the frozen Python `a.b.m(...)` source shape, not the broader `a.m(...)`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ConstructionV2Error(f"invalid Python provider source: {exc}") from exc
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node.lineno != anchor["start_line"]:
            continue
        text = ast.get_source_segment(source, node)
        if text == anchor["expression"]:
            matches.append(node)
    if len(matches) != 1:
        raise ConstructionV2Error(f"Python provider endpoint is not one exact call: {anchor}")
    function = matches[0].func
    if not isinstance(function, ast.Attribute) or not isinstance(function.value, ast.Attribute):
        raise ConstructionV2Error(
            f"call_typed_attribute endpoint must have frozen a.b.m(...) shape: {anchor}"
        )


def inside_python_function(source: str, anchor: dict) -> None:
    tree = ast.parse(source)
    line = anchor["start_line"]
    enclosing = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.lineno <= line <= (node.end_lineno or node.lineno)]
    if not enclosing:
        raise ConstructionV2Error(f"Python provider target is outside a function body: {anchor}")


def validate_provider_v2() -> dict:
    doc = load(PROVIDER)
    if doc.get("schema") != "rd-v3-provider-development/v2":
        raise ConstructionV2Error("bad provider development v2 schema")
    cases = doc.get("cases")
    if not isinstance(cases, list) or len(cases) != len(v1.ELIGIBLE_TARGETS):
        raise ConstructionV2Error("provider development v2 needs one case per eligible target")
    seen, source_text = set(), []
    for case in cases:
        target = case.get("target")
        if target in seen or target not in v1.ELIGIBLE_TARGETS:
            raise ConstructionV2Error(f"bad/duplicate provider target: {target}")
        seen.add(target)
        language, relation = v1.ELIGIBLE_TARGETS[target]
        if (case.get("language"), case.get("relation")) != (language, relation):
            raise ConstructionV2Error(f"provider target mapping drift: {target}")
        files = case.get("files")
        if not isinstance(files, dict) or not files:
            raise ConstructionV2Error(f"{target}: no provider source")
        for name, source in files.items():
            try:
                v1.syntax(language, source, f"{target}/{name}")
            except v1.ConstructionError as exc:
                raise ConstructionV2Error(str(exc)) from exc
            source_text.append(source)
        edges = case.get("edges")
        if not isinstance(edges, list) or len(edges) != 4 \
                or sum(edge.get("truth") is True for edge in edges) != 2 \
                or sum(edge.get("truth") is False for edge in edges) != 2:
            raise ConstructionV2Error(f"{target}: provider dev requires 2 true and 2 false")
        if len({edge.get("id") for edge in edges}) != len(edges):
            raise ConstructionV2Error(f"{target}: duplicate edge id")
        families = [edge.get("false_family") for edge in edges if edge.get("truth") is False]
        if len(families) != len(set(families)) or set(families) != v1.FALSE_FAMILIES[target]:
            raise ConstructionV2Error(f"{target}: false-family coverage drift: {families}")
        for edge in edges:
            if edge.get("truth") is False and not edge.get("false_family"):
                raise ConstructionV2Error(f"{target}/{edge.get('id')}: false edge needs family")
            for side in ("from", "to"):
                anchor = edge.get(side)
                source = files.get(anchor.get("file")) if isinstance(anchor, dict) else None
                if source is None:
                    raise ConstructionV2Error(f"{target}/{edge.get('id')}: unknown endpoint file")
                try:
                    v1.exact_line(source, anchor, statement=False)
                except v1.ConstructionError as exc:
                    raise ConstructionV2Error(str(exc)) from exc
            if target == "python_typed_attribute_dispatch":
                source = files[edge["from"]["file"]]
                nested_attribute_call(source, edge["from"])
                inside_python_function(files[edge["to"]["file"]], edge["to"])
    if seen != set(v1.ELIGIBLE_TARGETS):
        raise ConstructionV2Error("provider development v2 target coverage mismatch")
    joined = "\n".join(source_text)
    leaked = [token for token in v1.FORBIDDEN_SOURCE_TOKENS if token in joined]
    if leaked:
        raise ConstructionV2Error(f"provider development v2 contains v2 tokens: {leaked}")
    return {"schema": doc["schema"], "targets": len(seen),
            "true_edges": 2 * len(seen), "false_edges": 2 * len(seen),
            "python_source_shape": "a.b.m(...)"}


def validation() -> dict:
    missing = [str(path.relative_to(ROOT)) for path in BOUND if not path.exists()]
    if missing:
        raise ConstructionV2Error(f"missing bound files: {missing}")
    try:
        old = v1.verify()
        base = {"toolchain": v1.validate_go_toolchain(),
                "a_development": v1.validate_a(), "a_heldout": v1.validate_a_heldout(),
                "provider_heldout": v1.validate_provider_heldout(),
                "selection": v1.validate_selection()}
    except v1.ConstructionError as exc:
        raise ConstructionV2Error(f"construction v1 provenance failed: {exc}") from exc
    return {"superseded_v1": {"status": "CONSTRUCTION_INVALID",
                               "manifest_sha256": sha256(v1.FREEZE),
                               "created_from_commit": old["created_from_commit"]},
            **base, "provider_development": validate_provider_v2()}


def clean_tracked_tree() -> None:
    result = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                             "--untracked-files=no"], text=True, capture_output=True, check=True)
    if result.stdout.strip():
        raise ConstructionV2Error("tracked tree must be clean before construction v2 freeze write")


def build() -> dict:
    clean_tracked_tree()
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True,
                            capture_output=True, check=True).stdout.strip()
    checks = validation()
    return {"schema": "rd-v3-construction-freeze/v2", "protocol": "rd-v3",
            "status": "CONSTRUCTION_FROZEN", "supersedes": str(v1.FREEZE.relative_to(ROOT)),
            "created_from_commit": commit,
            "files": {str(path.relative_to(ROOT)): sha256(path) for path in BOUND},
            "validation": checks}


def write() -> None:
    if FREEZE.exists():
        raise ConstructionV2Error("construction freeze v2 already exists; do not overwrite")
    doc = build()
    FREEZE.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "WROTE", "commit": doc["created_from_commit"],
                      "files": len(doc["files"]), "validation": doc["validation"]}, indent=2))


def verify() -> dict:
    if not FREEZE.exists():
        raise ConstructionV2Error("construction freeze v2 is missing")
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
    except ConstructionV2Error as exc:
        problems.append(str(exc))
    if problems:
        raise ConstructionV2Error("; ".join(problems))
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
