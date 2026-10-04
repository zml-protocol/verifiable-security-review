"""RD v3 phase runtime: calibrated A, checkpointed B, and locked C1 then C2."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import schema as v2_schema  # noqa: E402
import session as v2_session  # noqa: E402
from spike.gitrepo import GitError  # noqa: E402
from spike.session import ToolInputError  # noqa: E402

import rdv3_calibration as calibration  # noqa: E402
import rdv3_checkpoint as checkpoint  # noqa: E402
import rdv3_contract as contract  # noqa: E402

SUBMISSION_TOOLS = {
    "submit_requirements", "submit_evidence", "submit_effect_attribution", "submit_cwe_taxonomy"
}


class EffectClaim(BaseModel):
    package: str
    effect_claim: str


class V3Config(BaseModel):
    protocol: Literal["rd-v3"] = "rd-v3"
    session_id: str
    task_id: str
    phase: Literal["a", "b", "c"]
    c_stage: Literal["c1", "c2"] | None = None
    language: Literal["go", "python"]
    claim: EffectClaim
    repo: str
    revisions: dict[str, str]
    deny_paths: list[str] = Field(default_factory=list)
    out_dir: str
    artifact_dir: str
    analysis: dict[str, str] = Field(default_factory=dict)
    provider_sha256: str = ""
    relation_table_sha256: str = ""


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolInputError("artifact_error", f"cannot read locked artifact {path.name}: {exc}") from None


class V3Session(v2_session.RDSession):
    config: V3Config

    def __init__(self, config: V3Config):
        self._checkpoint: checkpoint.CheckpointLog | None = None
        self._phase_started = time.monotonic()
        super().__init__(config)  # type: ignore[arg-type]
        if self.phase == "b":
            for name, value in (("provider_sha256", config.provider_sha256),
                                ("relation_table_sha256", config.relation_table_sha256)):
                if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                    raise ValueError(f"phase B requires canonical lowercase {name}")
            a = _read(self.a_path)
            self._checkpoint = checkpoint.CheckpointLog(
                self.artifact_dir / "b-checkpoints", task_id=config.task_id,
                session_id=config.session_id, a_seal=a["seal"],
                provider_sha256=config.provider_sha256,
                relation_table_sha256=config.relation_table_sha256,
            )
        elif self.phase == "c":
            if config.c_stage not in ("c1", "c2"):
                raise ValueError("phase C requires c_stage c1 or c2")
            submit = ("submit_effect_attribution" if config.c_stage == "c1"
                      else "submit_cwe_taxonomy")
            self._tools = {"get_task": self.tool_get_task, submit: getattr(self, f"tool_{submit}")}
        self._save_state()

    @property
    def c1_path(self) -> Path:
        return self.artifact_dir / "c1.json"

    @property
    def c2_path(self) -> Path:
        return self.artifact_dir / "c2.json"

    @property
    def partial_checkpoint_path(self) -> Path:
        return self.artifact_dir / "partial-checkpoint.json"

    @property
    def b_terminal_path(self) -> Path:
        return self.artifact_dir / "b-terminal.json"

    def _b_input_path(self) -> Path:
        if self.b_path.exists():
            return self.b_path
        return self.b_terminal_path

    def _verify_upstream(self) -> None:
        if self.phase in ("b", "c"):
            a = _read(self.a_path)
            contract.verify_seal(a)
            if a.get("task_id") != self.config.task_id:
                raise ToolInputError("artifact_error", "locked A belongs to another task")
        if self.phase == "c":
            b = _read(self._b_input_path())
            contract.verify_seal(b)
            if b.get("task_id") != self.config.task_id or b.get("a_seal") != a["seal"]:
                raise ToolInputError("artifact_error", "locked B input does not bind the current A")
            if b.get("schema") == "rd-v3-b-terminal/v1":
                partial = _read(self.partial_checkpoint_path)
                partial_seal = contract.verify_seal(partial)
                if b.get("status") != "B_TERMINAL_NO_SUBMIT" \
                        or b.get("partial_checkpoint_seal") != partial_seal:
                    raise ToolInputError("artifact_error", "terminal B checkpoint binding is invalid")
        if self.phase == "c" and self.c1_path.exists():
            c1 = _read(self.c1_path)
            contract.verify_seal(c1)
            if c1.get("task_id") != self.config.task_id:
                raise ToolInputError("artifact_error", "locked C1 belongs to another task")
        if self.phase == "c" and self.config.c_stage == "c2" and not self.c1_path.exists():
            raise ToolInputError("artifact_error", "C2 cannot start before C1 locks")

    def call(self, tool: str, **args: Any) -> Any:
        self._seq += 1
        event: dict[str, Any] = {"seq": self._seq, "ts": time.time(), "phase": self.phase,
                                 "tool": tool, "args": args}
        try:
            if tool not in self._tools:
                raise ToolInputError("unknown_tool", f"no such tool in phase {self.phase.upper()}: {tool}")
            if self.finished and tool != "get_task":
                raise ToolInputError("session_finished", "this phase is locked; end your turn")
            if tool not in SUBMISSION_TOOLS:
                self.calls += 1
                if self.calls > v2_session.LIMITS[self.phase]:
                    raise ToolInputError("call_limit", "the non-submission tool-call limit is exhausted")
            result = self._tools[tool](**args)
            event["result"] = result
            return result
        except (ToolInputError, v2_schema.SchemaError, v2_session.resolver.ResolverError,
                v2_session.hoplib.HopError, checkpoint.CheckpointError) as exc:
            code = getattr(exc, "code", "schema")
            event["error"] = {"code": code, "message": str(exc)}
            if isinstance(exc, ToolInputError):
                raise
            raise ToolInputError(code, str(exc)) from None
        except GitError:
            event["error"] = {"code": "git_error", "message": "repository read failed"}
            raise ToolInputError("git_error", "repository read failed") from None
        except Exception as exc:
            event["error"] = {"code": "internal_error", "message": repr(exc)}
            raise
        finally:
            with (self.out_dir / "transcript.jsonl").open("a") as stream:
                stream.write(json.dumps(event, default=str) + "\n")
            self._save_state()

    def _save_state(self) -> None:
        state = {"protocol": self.config.protocol, "session_id": self.config.session_id,
                 "task_id": self.config.task_id, "phase": self.phase,
                 "finished": self.finished, "non_submission_calls": self.calls,
                 "hop_checks": self.hop_checks,
                 "rejected_submissions": self.rejected_submissions,
                 "checked_hops": list(self.checked.values())}
        if self.phase == "c":
            state["c_stage"] = self.config.c_stage
            state["c_progress"] = ("complete" if self.c2_path.exists() else
                                   "c1_locked" if self.c1_path.exists() else "not_locked")
        (self.out_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n")

    def _claim(self) -> str:
        claim = self.config.claim
        return (f"Evaluate this plain-language security-effect claim in {claim.package}: "
                f"{claim.effect_claim}. Compare revision_A and revision_B, determine what must be "
                "proved to assess the claim, and finally decide how the change relates to that effect.")

    def tool_get_task(self) -> dict:
        if self.phase in ("a", "b"):
            base = super().tool_get_task()
            if self.phase == "a":
                base["schema_calibration"] = {
                    "purpose": "worked examples teach the representation contract, not this task's answer",
                    "examples": calibration.examples(self.config.language),
                    "hard_rules": [
                        "entry is the first claim-specific repository value, not an upstream container or later derivative",
                        "behavior is the complete deciding statement, not a computed value or subexpression",
                        "a changed statement present in both revisions is present/present with two exact anchors",
                        "absent uses the exact controlled or supplied statement as context",
                        "never substitute a field, subexpression, or enclosing function for the required statement",
                    ],
                }
            return base
        a, b = _read(self.a_path), _read(self._b_input_path())
        common = {"task": self._claim(), "revisions": [*contract.REVISIONS], "phase": "C",
                  "locked_A": {key: value for key, value in a.items() if key != "seal"},
                  "a_seal": a["seal"],
                  "locked_B": {key: value for key, value in b.items() if key != "seal"},
                  "b_seal": b["seal"]}
        if self.config.c_stage == "c1":
            return {**common, "stage": "C1_EFFECT_ATTRIBUTION",
                    "statuses": list(contract.ATTRIBUTION_STATUSES),
                    "submission_schema": {"revision_A": "<status>",
                                          "revision_B": "<status>",
                                          "rationale": "optional unscored text"},
                    "rules": ["attribute the stated plain-language security effect only",
                              "submit C1 before any taxonomy output; a successful C1 is immutable"]}
        c1 = _read(self.c1_path)
        contract.verify_seal(c1)
        return {**common, "stage": "C2_CWE_TAXONOMY",
                "locked_C1": {key: value for key, value in c1.items() if key != "seal"},
                "c1_seal": c1["seal"],
                "submission_schema": {
                    "ranked": {"ranked_cwes": ["CWE-<id>", "1 to 3 unique items"],
                               "rationale": "optional unscored text"},
                    "abstain": {"result": "NO_CONFIDENT_CWE",
                                "rationale": "optional unscored text"}},
                "rules": ["the frozen comparison label is hidden",
                          "submit exactly one ranked-list or abstention form",
                          "C2 cannot alter locked C1"]}

    def tool_check_hop(self, hop: dict) -> dict:
        self.hop_checks += 1
        assert self._checkpoint is not None
        elapsed_ms = int((time.monotonic() - self._phase_started) * 1000)
        if self.hop_checks > v2_session.MAX_HOP_CHECKS:
            self._checkpoint.append(
                proposed_hop=hop, state="REJECTED_LIMIT", elapsed_ms=elapsed_ms,
                tool_sequence=self._seq, hop_check=self.hop_checks,
                error={"code": "hop_check_limit", "message": "the 18-call hop-check limit is exhausted"},
            )
            raise ToolInputError("hop_check_limit", "the 18-call hop-check limit is exhausted")
        try:
            clean, state = self._check(hop)
        except (v2_schema.SchemaError, v2_session.resolver.ResolverError,
                v2_session.hoplib.HopError, ToolInputError) as exc:
            self._checkpoint.append(
                proposed_hop=hop, state="REJECTED_STRUCTURAL", elapsed_ms=elapsed_ms,
                tool_sequence=self._seq, hop_check=self.hop_checks,
                error={"code": getattr(exc, "code", "schema"), "message": str(exc)},
            )
            raise
        key = v2_schema.seal(clean)
        checked = {"hop_sha256": key, "hop": clean, "state": state}
        self.checked[key] = copy.deepcopy(checked)
        self._checkpoint.append(
            proposed_hop=hop, state=state, elapsed_ms=elapsed_ms,
            tool_sequence=self._seq, hop_check=self.hop_checks, checked=checked,
        )
        feedback = {"VERIFIED": "confirmed", "UNVERIFIED": "not confirmed",
                    "UNSUPPORTED": "unable to confirm"}[state]
        return {"feedback": feedback}

    def tool_submit_effect_attribution(self, conclusion: dict) -> dict:
        if self.c1_path.exists():
            raise ToolInputError("locked", "C1 is already locked")
        try:
            clean = contract.effect_attribution(conclusion)
        except contract.V3SchemaError as exc:
            self._reject_submission(exc)
            raise
        a, b = _read(self.a_path), _read(self._b_input_path())
        claim_hash = hashlib.sha256(self.config.claim.effect_claim.encode()).hexdigest()
        artifact = contract.sealed({
            "schema": "rd-v3-c1/v1", "task_id": self.config.task_id,
            "a_seal": a["seal"], "b_seal": b["seal"],
            "effect_claim_sha256": claim_hash, "conclusion": clean,
        })
        self.c1_path.write_text(json.dumps(artifact, indent=2) + "\n")
        self.finished = True
        return {"locked": "C1", "c1_seal": artifact["seal"],
                "next": "end your turn; C2 will resume in the same C budget envelope"}

    def tool_submit_cwe_taxonomy(self, taxonomy: dict) -> dict:
        if not self.c1_path.exists():
            raise ToolInputError("phase_order", "C1 must lock before C2")
        if self.c2_path.exists():
            raise ToolInputError("locked", "C2 is already locked")
        try:
            clean = contract.cwe_taxonomy(taxonomy)
        except contract.V3SchemaError as exc:
            self._reject_submission(exc)
            raise
        c1 = _read(self.c1_path)
        contract.verify_seal(c1)
        artifact = contract.sealed({
            "schema": "rd-v3-c2/v1", "task_id": self.config.task_id,
            "c1_seal": c1["seal"], "taxonomy": clean,
        })
        self.c2_path.write_text(json.dumps(artifact, indent=2) + "\n")
        self.finished = True
        return {"locked": "C2", "c2_seal": artifact["seal"], "next": "end your turn"}
