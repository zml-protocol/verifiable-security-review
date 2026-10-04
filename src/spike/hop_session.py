"""One P-Hybrid-2 hop session (PREREGISTRATION.md §11): the read tools of `Session`, plus
`validate_hop` and `submit_hops`.

Phase `initial`: the agent may submit once; a successful submission locks the initial hops.
Phase `final`: a forked revision session; the locked initial hops are restored from the
parent's snapshot and the agent may submit its final hops once. Validation is the runtime's
shared interface (schema, anchor, node kind) and never reports a relation verdict.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Literal

from . import hops as hoplib
from .models import SessionConfig
from .session import Session, ToolInputError

HOP_TOOLS = (
    "get_task", "list_files", "read_code", "search_code", "find_symbol",
    "changed_files", "diff_file", "map_location", "validate_hop", "submit_hops",
)  # fmt: skip

HOP_FORMAT = """\
A hop is one typed link between two places in ONE revision:
  {"revision": "base" | "head", "relation": <relation id>,
   "from": {"file": <path>, "start_line": <n>, "end_line": <m>, "expression": <code>},
   "to":   {"file": <path>, "start_line": <n>, "end_line": <m>, "expression": <code>}}
- expression: code text copied from lines start_line..end_line of that file in that
  revision. Whitespace differences do not matter, but it must occur exactly once in those
  lines. The place an endpoint names is where its expression STARTS.
- Each relation says which kind of code each endpoint must name (relations, kinds)."""

RULES = {
    "initial": """\
- Lay out, at BOTH revisions, how the hinted entry point reaches the code that decides the
  behavior the hypothesis describes, as a chain of typed hops (see hop_format).
- You are not asked whether the hypothesis holds; give no verdict.
- validate_hop checks one hop's format and node kinds. submit_hops takes your whole set at
  once: at most {max_hops} distinct hops, every one passing validate_hop. A successful
  submit_hops locks your hops.
- After a successful submit_hops, end your turn.""",
    "final": """\
- Your initial hops (below) are locked. This is your one revision: keep, fix, drop or add
  hops, then call submit_hops once with your complete final set (same format and limits:
  at most {max_hops} distinct hops, every one passing validate_hop).
- You are not asked whether the hypothesis holds; give no verdict.
- After a successful submit_hops, end your turn.""",
}


class HopConfig(SessionConfig):
    language: Literal["go", "python"]
    phase: Literal["initial", "final"]
    relations: dict[str, dict]  # frozen spec: language, roles, kinds (relations.yaml)
    vocabulary: dict[str, dict[str, str]]  # agent-facing text: relations, kinds
    analysis: dict[str, str]  # revision -> frozen analysis (json.gz)
    initial_snapshot: str | None = None  # the parent's locked state (final phase only)
    max_hops: int = 12
    contract: str | None = None  # §13 semantic task contract; absent before §13


def _render_endpoint(ep: dict) -> str:
    lines = (f"{ep['start_line']}" if ep["start_line"] == ep["end_line"]
             else f"{ep['start_line']}-{ep['end_line']}")
    return f"{ep['file']}:{lines} `{ep['expression']}`"


def render_hop(hop: dict) -> str:
    return (f"{hop['id']}  {hop['revision']}  {hop['relation']}\n"
            f"    from {_render_endpoint(hop['from'])}\n    to   {_render_endpoint(hop['to'])}")


class HopSession(Session):
    def __init__(self, config: HopConfig):
        self.hop_config = config
        self.relations = {n: r for n, r in config.relations.items()
                          if r["language"] == config.language}
        self.analysis = {side: json.loads(gzip.decompress(Path(p).read_bytes()))
                         for side, p in config.analysis.items()}
        self.initial: list[dict] | None = None
        self.final: list[dict] | None = None
        self.validations = 0
        if config.phase == "final":
            if not config.initial_snapshot:
                raise ValueError("a final-phase session needs the parent's snapshot")
            snap = json.loads(Path(config.initial_snapshot).read_text())
            self.initial = snap["initial"] or []
        super().__init__(config)
        self._tools = {name: getattr(self, f"tool_{name}") for name in HOP_TOOLS}

    def _save_state(self) -> None:
        state = {
            "session_id": self.config.session_id,
            "hypothesis_id": self.hypothesis.id,
            "commits": self.commits,
            "phase": self.hop_config.phase,
            "initial": self.initial,
            "final": self.final,
            "validations": self.validations,
            "anchors": self.anchors.audit_records(),
        }
        (self.out_dir / "state.json").write_text(json.dumps(state, indent=2))

    # ---- hop checking ------------------------------------------------------

    def _text(self, revision: str, file: str) -> str | None:
        try:
            return "\n".join(self._lines(self._side(revision), file))
        except ToolInputError:
            return None

    def check(self, hop: Any) -> dict:
        """Canonical hop, or HopError: schema, anchor and node kinds only."""
        hop = hoplib.normalize(hop, self.relations, self.hop_config.language)
        for side in ("from", "to"):
            if not self._allowed(hop[side]["file"]):
                raise hoplib.HopError("anchor", f"{hop[side]['file']} is not available in this review")
        try:
            hoplib.resolve(hop, self._text, self.relations, self.analysis[hop["revision"]],
                         self.hop_config.language)
        except hoplib.HopError as e:
            if e.code == "not_analyzed":
                raise hoplib.HopError("not_analyzed", f"{e}; a hop there can only be declared "
                                    f"with relation '{hoplib.UNSUPPORTED}'") from None
            raise
        return hop

    # ---- tools ---------------------------------------------------------------

    def tool_get_task(self) -> dict:
        task = super().tool_get_task()
        phase = self.hop_config.phase
        task["hop_format"] = HOP_FORMAT
        task["relations"] = {
            name: {"description": self.hop_config.vocabulary["relations"][name].strip(),
                   **({"from": spec["from"]["kinds"], "to": spec["to"]["kinds"]}
                      if name in self.relations else {})}
            for name, spec in {**self.relations, hoplib.UNSUPPORTED: {}}.items()
        }
        kinds = sorted({k for s in self.relations.values() for side in ("from", "to")
                        for k in s[side]["kinds"]})
        task["kinds"] = {k: self.hop_config.vocabulary["kinds"][k] for k in kinds}
        task["rules"] = RULES[phase].format(max_hops=self.hop_config.max_hops)
        if phase == "final":
            task["initial_hops"] = "\n".join(render_hop(h) for h in self.initial or []) or "(none)"
        if self.hop_config.contract:
            task["verification_contract"] = self.hop_config.contract
        return task

    def tool_validate_hop(self, hop: Any) -> dict:
        self.validations += 1
        try:
            canonical = self.check(hop)
        except hoplib.HopError as e:
            return {"ok": False, "problem": f"[{e.code}] {e}"}
        return {"ok": True, "hop": canonical}

    def tool_submit_hops(self, hops: list[Any]) -> dict:
        phase = self.hop_config.phase
        if (self.initial if phase == "initial" else self.final) is not None:
            raise ToolInputError("locked", f"your {phase} hops are already locked; end your turn")
        if not isinstance(hops, list):
            raise ToolInputError("schema", "submit a list of hops")
        canonical, problems, seen = [], [], set()
        for i, hop in enumerate(hops, 1):
            try:
                c = self.check(hop)
            except hoplib.HopError as e:
                problems.append(f"hop #{i}: [{e.code}] {e}")
                continue
            if hoplib.key(c) not in seen:  # a duplicate is dropped, not counted
                seen.add(hoplib.key(c))
                canonical.append(c)
        if problems:
            raise ToolInputError("invalid_hops", "nothing was locked:\n" + "\n".join(problems))
        if len(canonical) > self.hop_config.max_hops:
            raise ToolInputError("too_many_hops", f"{len(canonical)} distinct hops; at most "
                                 f"{self.hop_config.max_hops}. Nothing was locked.")
        prefix = "h" if phase == "initial" else "f"
        locked = [{"id": f"{prefix}{i}", **h} for i, h in enumerate(canonical, 1)]
        if phase == "initial":
            self.initial = locked
        else:
            self.final = locked
        return {"locked": phase, "hops": "\n".join(render_hop(h) for h in locked) or "(none)",
                "next": "end your turn"}
