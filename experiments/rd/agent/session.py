"""Stateful, phase-scoped runtime for one RD task.

Each phase is served by a fresh MCP process.  The only shared state is the
sealed A/B artifact directory named in :class:`RDConfig`.
"""

from __future__ import annotations

import copy
import gzip
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
TRUTH = ROOT / "experiments" / "rd" / "truth"
for directory in (TRUTH, ROOT / "experiments" / "hop_bridge"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import resolver  # noqa: E402
import verifiability  # noqa: E402
from spike import hops as hoplib  # noqa: E402
from spike.gitrepo import GitError  # noqa: E402
from spike.session import ToolInputError  # noqa: E402

import schema  # noqa: E402
from source import SourceSurface  # noqa: E402

PHASES = ("a", "b", "c")
READ_TOOLS = ("get_task", "list_files", "read_code", "search_code", "find_symbol",
              "changed_files", "diff_file", "map_location")
SUBMIT_TOOLS = {"a": "submit_requirements", "b": "submit_evidence", "c": "submit_conclusion"}
LIMITS = {"a": 60, "b": 40, "c": 2}
MAX_HOP_CHECKS = 18
MAX_HOPS = 12
MAX_REJECTED_SUBMISSIONS = 3


class Claim(BaseModel):
    package: str
    cwe: int
    cwe_name: str


class RDConfig(BaseModel):
    protocol: Literal["rd-v2"] = "rd-v2"
    session_id: str
    task_id: str
    phase: Literal["a", "b", "c"]
    language: Literal["go", "python"]
    claim: Claim
    repo: str
    revisions: dict[str, str]
    deny_paths: list[str] = Field(default_factory=list)
    out_dir: str
    artifact_dir: str
    analysis: dict[str, str] = Field(default_factory=dict)


def relation_specs(language: str) -> dict[str, dict]:
    p1 = yaml.safe_load((ROOT / "experiments/hop_verify/relations.yaml").read_text())["relations"]
    bridge = yaml.safe_load((ROOT / "experiments/hop_bridge/relations.yaml").read_text())["relations"]
    out = {name: spec for name, spec in p1.items() if spec["language"] == language}
    out |= {name: {**spec, "language": language} for name, spec in bridge[language].items()}
    return out


def relation_public(language: str) -> dict[str, dict]:
    return {
        name: {"meaning": " ".join(spec["truth"].split()),
               "from_kinds": spec["from"]["kinds"], "to_kinds": spec["to"]["kinds"]}
        for name, spec in relation_specs(language).items()
    }


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise ToolInputError("artifact_error", f"cannot read locked artifact {path.name}: {e}") from None


class RDSession:
    def __init__(self, config: RDConfig):
        self.config = config
        self.phase = config.phase
        self.out_dir = Path(config.out_dir)
        self.artifact_dir = Path(config.artifact_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.source = (SourceSurface(config.repo, config.revisions, config.deny_paths)
                       if self.phase in ("a", "b") else None)
        self.relations = relation_specs(config.language) if self.phase == "b" else {}
        self.analysis = self._load_analysis() if self.phase == "b" else {}
        self.finished = False
        self.calls = 0
        self.hop_checks = 0
        self.rejected_submissions = 0
        self.checked: dict[str, dict] = {}
        self._seq = 0
        common = {"get_task": self.tool_get_task}
        if self.phase in ("a", "b"):
            common |= {name: getattr(self, f"tool_{name}") for name in READ_TOOLS if name != "get_task"}
        if self.phase == "a":
            common["submit_requirements"] = self.tool_submit_requirements
        elif self.phase == "b":
            common |= {"check_hop": self.tool_check_hop, "submit_evidence": self.tool_submit_evidence}
        else:
            common["submit_conclusion"] = self.tool_submit_conclusion
        self._tools: dict[str, Callable[..., Any]] = common
        self._verify_upstream()
        self._save_state()

    @property
    def a_path(self) -> Path:
        return self.artifact_dir / "a.json"

    @property
    def b_path(self) -> Path:
        return self.artifact_dir / "b.json"

    @property
    def c_path(self) -> Path:
        return self.artifact_dir / "c.json"

    def _verify_upstream(self) -> None:
        if self.phase in ("b", "c"):
            a = _read_json(self.a_path)
            schema.verify_seal(a)
            if a.get("task_id") != self.config.task_id:
                raise ToolInputError("artifact_error", "locked A belongs to another task")
        if self.phase == "c":
            b = _read_json(self.b_path)
            schema.verify_seal(b)
            if b.get("task_id") != self.config.task_id or b.get("a_seal") != a["seal"]:
                raise ToolInputError("artifact_error", "locked B does not bind the current A")

    def _load_analysis(self) -> dict:
        if set(self.config.analysis) != set(schema.REVISIONS):
            raise ValueError("phase B requires analysis for both revisions")
        out = {}
        for rev, name in self.config.analysis.items():
            p = Path(name)
            try:
                doc = json.loads(gzip.decompress(p.read_bytes()))
            except (OSError, json.JSONDecodeError) as e:
                raise ValueError(f"bad analysis {p}: {e}") from None
            if doc.get("status") != "ok" or doc.get("commit") != self.config.revisions[rev]:
                raise ValueError(f"analysis provenance mismatch for {rev}")
            out[rev] = doc
        return out

    def call(self, tool: str, **args: Any) -> Any:
        self._seq += 1
        event: dict[str, Any] = {"seq": self._seq, "ts": time.time(), "phase": self.phase,
                                 "tool": tool, "args": args}
        try:
            if tool not in self._tools:
                raise ToolInputError("unknown_tool", f"no such tool in phase {self.phase.upper()}: {tool}")
            if self.finished and tool != "get_task":
                raise ToolInputError("session_finished", "this phase is locked; end your turn")
            if tool not in SUBMIT_TOOLS.values():
                self.calls += 1
                if self.calls > LIMITS[self.phase]:
                    raise ToolInputError("call_limit", "the non-submission tool-call limit is exhausted")
            result = self._tools[tool](**args)
            event["result"] = result
            return result
        except (ToolInputError, schema.SchemaError, resolver.ResolverError, hoplib.HopError) as e:
            code = getattr(e, "code", "schema")
            event["error"] = {"code": code, "message": str(e)}
            if isinstance(e, ToolInputError):
                raise
            raise ToolInputError(code, str(e)) from None
        except GitError:
            event["error"] = {"code": "git_error", "message": "repository read failed"}
            raise ToolInputError("git_error", "repository read failed") from None
        except Exception as e:
            event["error"] = {"code": "internal_error", "message": repr(e)}
            raise
        finally:
            with (self.out_dir / "transcript.jsonl").open("a") as f:
                f.write(json.dumps(event, default=str) + "\n")
            self._save_state()

    def _save_state(self) -> None:
        state = {"protocol": self.config.protocol, "session_id": self.config.session_id,
                 "task_id": self.config.task_id, "phase": self.phase, "finished": self.finished,
                 "non_submission_calls": self.calls, "hop_checks": self.hop_checks,
                 "rejected_submissions": self.rejected_submissions,
                 "checked_hops": list(self.checked.values())}
        (self.out_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n")

    def _claim(self) -> str:
        c = self.config.claim
        return (f"Evaluate this claim: in {c.package}, attacker-controlled input may lead to "
                f"CWE-{c.cwe} {c.cwe_name}. Compare revision_A and revision_B, determine what "
                "must be proved to assess the claim, and finally decide how the change between "
                "the revisions relates to that behavior.")

    def tool_get_task(self) -> dict:
        base = {"task": self._claim(), "revisions": [*schema.REVISIONS], "phase": self.phase.upper()}
        if self.phase == "a":
            base |= {
                "definitions": {
                    "entry": "where the attacker-controlled input first becomes a value in repository code",
                    "behavior": "the program point that decides the security-relevant effect for the triggering input",
                    "absent_context": "the corresponding statement where the absent element would control or supply the path",
                    "guard": "a required property of an object on the path",
                    "config": "a required configuration condition outside the code path",
                    "dispatch_target": "the implementation a dynamic call must reach",
                },
                "rules": ["submit one entry and one behavior; each slot covers both revisions with present or absent",
                          "submit zero to six qualifier proposals; at most two may be UNSUPPORTED_REQUIREMENT_TYPE",
                          "copy exact whole statements into statement-granularity anchors",
                          "a successful submission locks Phase A"],
                "submission_schema": {
                    "entry": {rev: {"state": "present", "anchor": {
                        "file": "path", "start_line": 1, "end_line": 1,
                        "expression": "exact whole statement"}} for rev in schema.REVISIONS},
                    "behavior": {
                        "revision_A": {"state": "present", "anchor": {
                            "file": "path", "start_line": 1, "end_line": 1,
                            "expression": "exact whole statement"}},
                        "revision_B": {"state": "absent", "context": {
                            "file": "path", "start_line": 1, "end_line": 1,
                            "expression": "exact counterpart statement"}},
                    },
                    "required_qualifiers": [], "rationale": "optional unscored text",
                    "qualifier_shapes": {
                        "guard": {"kind": "guard", "expected": "must_hold|must_not_hold",
                                  "subject": "<revision slot>", "predicate": "<revision slot>"},
                        "config": {"kind": "config", "expected_condition": {
                            "op": "equals|not_equals|set|unset", "value": "literal when required"},
                                   "subject": "<revision slot>", "config": "<revision slot>"},
                        "dispatch_target": {"kind": "dispatch_target", "call": "<revision slot>",
                                            "target": "<revision slot>"},
                        "unsupported": {"kind": "UNSUPPORTED_REQUIREMENT_TYPE", "note": "why"},
                    },
                },
            }
        elif self.phase == "b":
            a = _read_json(self.a_path)
            base |= {"locked_A": {k: v for k, v in a.items() if k != "seal"}, "a_seal": a["seal"],
                     "relations": relation_public(self.config.language),
                     "unsupported": "Use relation 'unsupported' only when no listed relation describes the link.",
                     "rules": [f"check at most {MAX_HOP_CHECKS} hops; feedback is closed",
                               f"submit at most {MAX_HOPS} distinct byte-identically checked hops",
                               "connect the locked entry to locked behavior in each applicable revision",
                               "attach every locked present qualifier to the same graph",
                               "a successful submission locks Phase B"]}
        else:
            a, b = _read_json(self.a_path), _read_json(self.b_path)
            base |= {"locked_A": {k: v for k, v in a.items() if k != "seal"}, "a_seal": a["seal"],
                     "locked_B": {k: v for k, v in b.items() if k != "seal"}, "b_seal": b["seal"],
                     "statuses": list(schema.ATTRIBUTION_STATUSES),
                     "submission_schema": {"revision_A": "<status>", "revision_B": "<status>",
                                           "rationale": "optional unscored text"},
                     "rules": ["use only the locked A and B snapshots and your existing conversation context",
                               "submit one status for each revision; a successful submission locks Phase C"]}
        return base

    # Source tools are intentionally thin: their one implementation is shared by A and B.
    def tool_list_files(self, revision: str, prefix: str = "", limit: int = 300) -> dict:
        return self.source.list_files(revision, prefix, limit)  # type: ignore[union-attr]

    def tool_read_code(self, revision: str, path: str, start_line: int = 1,
                       end_line: int | None = None) -> dict:
        return self.source.read_code(revision, path, start_line, end_line)  # type: ignore[union-attr]

    def tool_search_code(self, revision: str, pattern: str, path_glob: str | None = None,
                         ignore_case: bool = False) -> dict:
        return self.source.search_code(revision, pattern, path_glob, ignore_case)  # type: ignore[union-attr]

    def tool_find_symbol(self, revision: str, name: str, path_glob: str | None = None) -> dict:
        return self.source.find_symbol(revision, name, path_glob)  # type: ignore[union-attr]

    def tool_changed_files(self) -> dict:
        return self.source.changed_files()  # type: ignore[union-attr]

    def tool_diff_file(self, path: str) -> dict:
        return self.source.diff_file(path)  # type: ignore[union-attr]

    def tool_map_location(self, from_revision: str, path: str, line: int) -> dict:
        return self.source.map_location(from_revision, path, line)  # type: ignore[union-attr]

    def _resolve_anchor(self, revision: str, a: dict) -> tuple:
        text = self.source.text(revision, a["file"])  # type: ignore[union-attr]
        if text is None:
            raise resolver.ResolverError(f"{a['file']} does not exist in {revision}")
        return resolver.resolve_identity(a, language=self.config.language, revision=revision, source=text)

    def _reject_submission(self, error: Exception) -> None:
        self.rejected_submissions += 1
        if self.rejected_submissions >= MAX_REJECTED_SUBMISSIONS:
            self.finished = True
            raise ToolInputError("submission_limit", f"third rejected submission: {error}") from None

    def tool_submit_requirements(self, requirements: dict) -> dict:
        if self.a_path.exists():
            raise ToolInputError("locked", "Phase A is already locked")
        try:
            clean = schema.requirements(requirements, self._resolve_anchor)
        except (schema.SchemaError, resolver.ResolverError, ToolInputError) as e:
            self._reject_submission(e)
            raise
        artifact = schema.sealed({"schema": "rd-a/v1", "task_id": self.config.task_id,
                                  "requirements": clean})
        self.a_path.write_text(json.dumps(artifact, indent=2) + "\n")
        self.finished = True
        return {"locked": "A", "a_seal": artifact["seal"], "next": "end your turn"}

    def _internal_hop(self, h: dict) -> dict:
        out = copy.deepcopy(h)
        out["revision"] = "base" if h["revision"] == "revision_A" else "head"
        return out

    def _text_internal(self, revision: str, file: str) -> str | None:
        outward = "revision_A" if revision == "base" else "revision_B"
        try:
            return self.source.text(outward, file)  # type: ignore[union-attr]
        except ToolInputError:
            return None

    def _check(self, value: dict) -> tuple[dict, str]:
        h = schema.hop(value, set(self.relations))
        internal = self._internal_hop(h)
        canonical = hoplib.normalize(internal, self.relations, self.config.language)
        rev = h["revision"]
        resolved = hoplib.resolve(canonical, self._text_internal, self.relations,
                                  self.analysis[rev], self.config.language)
        if h["relation"] == "unsupported" or not verifiability.verifiable_pair(
                self.config.language, h["relation"]):
            state = "UNSUPPORTED"
        else:
            state = hoplib.verdict(canonical, resolved, self.relations, self.analysis[rev])
        return h, state

    def tool_check_hop(self, hop: dict) -> dict:
        self.hop_checks += 1
        if self.hop_checks > MAX_HOP_CHECKS:
            raise ToolInputError("hop_check_limit", "the 18-call hop-check limit is exhausted")
        h, state = self._check(hop)
        key = schema.seal(h)
        self.checked[key] = {"hop_sha256": key, "hop": h, "state": state}
        feedback = {"VERIFIED": "confirmed", "UNVERIFIED": "not confirmed",
                    "UNSUPPORTED": "unable to confirm"}[state]
        return {"feedback": feedback}

    def tool_submit_evidence(self, hops: list[dict], requirement_doubt: str | None = None) -> dict:
        if self.b_path.exists():
            raise ToolInputError("locked", "Phase B is already locked")
        try:
            if not isinstance(hops, list):
                raise schema.SchemaError("hops must be a list")
            clean, seen = [], set()
            for i, value in enumerate(hops, 1):
                h = schema.hop(value, set(self.relations))
                key = schema.seal(h)
                if key not in self.checked:
                    raise schema.SchemaError(f"hop #{i} was not checked byte-identically in this B turn")
                if key not in seen:
                    clean.append(copy.deepcopy(self.checked[key]))
                    seen.add(key)
            if len(clean) > MAX_HOPS:
                raise schema.SchemaError(f"{len(clean)} distinct hops; at most {MAX_HOPS}")
            if requirement_doubt is not None and not isinstance(requirement_doubt, str):
                raise schema.SchemaError("requirement_doubt must be a string or null")
        except schema.SchemaError as e:
            self._reject_submission(e)
            raise
        a = _read_json(self.a_path)
        artifact = schema.sealed({"schema": "rd-b/v1", "task_id": self.config.task_id,
                                  "a_seal": a["seal"], "hops": clean,
                                  "requirement_doubt": (requirement_doubt or "").strip() or None})
        self.b_path.write_text(json.dumps(artifact, indent=2) + "\n")
        self.finished = True
        return {"locked": "B", "b_seal": artifact["seal"], "next": "end your turn"}

    def tool_submit_conclusion(self, conclusion: dict) -> dict:
        if self.c_path.exists():
            raise ToolInputError("locked", "Phase C is already locked")
        try:
            clean = schema.conclusion(conclusion)
        except schema.SchemaError as e:
            self._reject_submission(e)
            raise
        a, b = _read_json(self.a_path), _read_json(self.b_path)
        artifact = schema.sealed({"schema": "rd-c/v1", "task_id": self.config.task_id,
                                  "a_seal": a["seal"], "b_seal": b["seal"],
                                  "conclusion": clean})
        self.c_path.write_text(json.dumps(artifact, indent=2) + "\n")
        self.finished = True
        return {"locked": "C", "c_seal": artifact["seal"], "next": "end your turn"}
