"""RD v3 analysis wrapper: frozen v2 relations with two bounded query replacements."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))


def local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v2_analysis = local_module("rd_v2_analysis_for_v3", PARENT / "analysis.py")
V2_QUERIES = v2_analysis._queries

OVERRIDES = {
    ("go", "argument_binding"): HERE / "queries" / "go" / "ArgumentBinding.ql",
    ("python", "call_typed_attribute"): HERE / "queries" / "python" / "CallTarget.ql",
}


def queries(language: str) -> tuple[list[Path], dict[str, Path]]:
    shapes, relations = V2_QUERIES(language)
    out = dict(relations)
    for (target_language, relation), path in OVERRIDES.items():
        if target_language == language:
            out[relation] = path
    return shapes, out


def build_spec(task: dict, task_id: str, revision: str, out_dir: Path) -> Path:
    original = v2_analysis._queries
    v2_analysis._queries = queries
    try:
        return v2_analysis.build_spec(task, task_id, revision, out_dir)
    finally:
        v2_analysis._queries = original
