from pathlib import Path

import pytest

from spike.anchors import Anchor
from spike.derive import attribute, component_status, derive, revision_status
from spike.gitrepo import GitRepo
from spike.golden import check_golden, expected
from spike.linemap import LineMap
from spike.models import Golden, Observation

ROOT = Path(__file__).resolve().parents[1]


def obs(side, comp, stance, path="app/notes.py", lines=(1, 1)):
    anchor = Anchor(id="A0", revision=side, path=path, start_line=lines[0], end_line=lines[1], sha256="")
    return Observation(id="O", seq=0, revision=side, component=comp, stance=stance,
                       statement="", citations=[anchor])


def test_component_and_revision_status():
    o = [obs("head", "a", "supports"), obs("head", "b", "supports"), obs("head", "b", "contradicts"),
         obs("head", "c", "unclear")]
    assert component_status(o, "head", "a") == "supported"
    assert component_status(o, "head", "b") == "conflicted"
    assert component_status(o, "head", "c") == "no_evidence"
    assert revision_status({"a": "supported", "b": "supported"}) == "SUPPORTED"
    assert revision_status({"a": "supported", "b": "no_evidence"}) == "INCOMPLETE"
    assert revision_status({"a": "conflicted", "b": "contradicted"}) == "CONTRADICTED"
    assert revision_status({"a": "conflicted", "b": "supported"}) == "CONFLICTED"
    assert revision_status({"a": "no_evidence"}) == "NO_EVIDENCE"


@pytest.mark.parametrize("base,head,implicated,want", [
    ("SUPPORTED", "SUPPORTED", False, "PRE_EXISTING"),
    ("CONTRADICTED", "SUPPORTED", True, "CHANGE_IMPLICATED"),
    ("CONTRADICTED", "SUPPORTED", False, "UNATTRIBUTED"),
    ("NO_EVIDENCE", "SUPPORTED", True, "UNATTRIBUTED"),  # absence of evidence is not refutation
    ("SUPPORTED", "CONTRADICTED", True, "FIX_IMPLICATED"),
    ("CONTRADICTED", "CONTRADICTED", False, "NOT_SUPPORTED"),
    ("SUPPORTED", "INCOMPLETE", False, "UNDETERMINED"),
])
def test_attribute(base, head, implicated, want):
    assert attribute(base, head, implicated) == want


def test_change_implicated_needs_evidence_on_changed_lines(notes_repo):
    repo = GitRepo(notes_repo)
    lm = LineMap(repo, repo.resolve("base"), repo.resolve("head"))
    comps = ["entrypoint", "control", "effect"]
    common = [obs(s, c, "supports", lines=(14, 16)) for s in ("base", "head") for c in ("entrypoint", "effect")]
    # the flip is evidenced on lines the change rewrote (base 17-20, head 17)
    on_diff = common + [obs("base", "control", "contradicts", lines=(18, 19)),
                        obs("head", "control", "supports", lines=(17, 17))]
    assert derive(on_diff, comps, lm)["attribution"] == "CHANGE_IMPLICATED"
    # same flip, but every citation sits on untouched lines
    off_diff = common + [obs("base", "control", "contradicts", path="app/web.py", lines=(20, 24)),
                         obs("head", "control", "supports", path="app/web.py", lines=(20, 24))]
    assert derive(off_diff, comps, lm)["attribution"] == "UNATTRIBUTED"


def test_fixture_goldens_are_consistent():
    for golden_path in ROOT.glob("fixtures/*/golden.yaml"):
        assert check_golden(Golden.load(golden_path)) == []


def test_expected_under_metamorphic_conditions():
    g = Golden.load(ROOT / "fixtures/synthetic-notes/golden.yaml").hypotheses
    assert [expected(g["H1"], c)["attribution"] for c in
            ("forward", "swapped", "identity_base", "identity_head")] == [
        "CHANGE_IMPLICATED", "FIX_IMPLICATED", "NOT_SUPPORTED", "PRE_EXISTING"]
    assert {expected(g["H3"], c)["attribution"] for c in ("forward", "swapped")} == {"PRE_EXISTING"}
    assert {expected(g["H4"], c)["attribution"] for c in ("forward", "swapped")} == {"NOT_SUPPORTED"}
    swapped = {f.id: f.revision for f in expected(g["H1"], "swapped")["facts"]}
    assert swapped == {"base-delete-owner-check@head": "head", "head-delete-path-unchecked@base": "base"}
    identity = [f.id for f in expected(g["H1"], "identity_head")["facts"]]
    assert identity == ["head-delete-path-unchecked@base", "head-delete-path-unchecked@head"]
