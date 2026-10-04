"""Spike-grade data models. Deliberately loose: Phase 0 goldens decide the real schema."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .anchors import Anchor

Side = Literal["base", "head"]
Stance = Literal["supports", "contradicts", "unclear"]


class Component(BaseModel):
    id: str
    text: str


class Hint(BaseModel):
    """A starting location, as a candidate generator would emit it.

    Hints must look like what Spike 1A could actually produce (entrypoint,
    sink); pointing at the control that decides the answer leaks the golden.
    They name no revision, so base/head swapping never has to rewrite them.
    """

    path: str
    symbol: str | None = None
    note: str | None = None


class Hypothesis(BaseModel):
    id: str
    property_kind: str
    claim: str
    components: list[Component]
    hints: list[Hint] = []


class RepoSpec(BaseModel):
    path: str | None = None  # local clone, relative to the project root
    url: str | None = None


class CaseSpec(BaseModel):
    id: str
    kind: Literal["synthetic", "structural", "semantic"]
    repo: RepoSpec
    base: str
    head: str
    deny_paths: list[str] = []
    hypotheses: list[Hypothesis]
    notes: str = ""

    @classmethod
    def load(cls, path: str | Path) -> CaseSpec:
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class SessionConfig(BaseModel):
    """Everything one agent run needs. Written by the runner, read by the MCP server."""

    session_id: str
    repo: str
    revisions: dict[Side, str]  # refs or SHAs; resolved to SHAs at session start
    hypothesis: Hypothesis
    deny_paths: list[str] = []
    out_dir: str
    max_read_lines: int = 200
    max_search_hits: int = 50


class Observation(BaseModel):
    id: str
    seq: int
    revision: Side
    component: str
    stance: Stance
    statement: str
    citations: list[Anchor] = Field(default_factory=list)


class BlindSpot(BaseModel):
    id: str
    seq: int
    revision: Side
    component: str | None
    description: str
    citations: list[Anchor] = Field(default_factory=list)


class EvidenceLocation(BaseModel):
    path: str
    lines: str | int  # "18-19" or 18

    def span(self) -> tuple[int, int]:
        a, _, b = str(self.lines).partition("-")
        return int(a), int(b or a)


class Fact(BaseModel):
    """A security-relevant fact that a correct investigation must establish.

    Any one evidence set suffices; every location in the chosen set must be cited.
    """

    id: str
    revision: Side
    component: str
    statement: str
    evidence_sets: list[list[EvidenceLocation]]


class GoldenHypothesis(BaseModel):
    truth: dict[Side, bool]
    components: dict[str, dict[Side, Literal["supported", "contradicted"]]]
    attribution: dict[Literal["static_only", "with_execution"], str]
    facts: list[Fact] = []


class Golden(BaseModel):
    """Expected answers for a case, stated for its original base/head."""

    case: str
    hypotheses: dict[str, GoldenHypothesis]

    @classmethod
    def load(cls, path: str | Path) -> Golden:
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
