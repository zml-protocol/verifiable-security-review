import importlib.util
from pathlib import Path

import pytest

from spike.models import CaseSpec, SessionConfig
from spike.session import Session

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "synthetic-notes"


def _load_builder():
    spec = importlib.util.spec_from_file_location("synthetic_build", FIXTURE / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def notes_repo(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("fixtures") / "synthetic-notes"
    _load_builder().build(dest)
    return dest


@pytest.fixture(scope="session")
def notes_case() -> CaseSpec:
    return CaseSpec.load(FIXTURE / "case.yaml")


@pytest.fixture
def make_session(notes_repo, notes_case, tmp_path):
    def make(hypothesis="H1", base="base", head="head", deny=()):
        hyp = next(h for h in notes_case.hypotheses if h.id == hypothesis)
        config = SessionConfig(
            session_id="test",
            repo=str(notes_repo),
            revisions={"base": base, "head": head},
            hypothesis=hyp,
            deny_paths=list(deny),
            out_dir=str(tmp_path / "run"),
        )
        return Session(config)

    return make
