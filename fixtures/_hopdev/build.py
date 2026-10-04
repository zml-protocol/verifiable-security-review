"""Build the hop-verifier development modules (NOT evaluation fixtures).

    uv run python fixtures/_hopdev/build.py   # -> .cache/fixtures/hopdev-{go,py}, tags base/head

The verifiers of PREREGISTRATION.md §10 were developed against these modules
only. They share no code with Authlib, Caddy or File Browser. Each head commit
replaces a few lines without moving any other line, so a hop copied to the
other revision keeps its text while the relation it claims may change.
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GO_MOD = "module example.com/hopdev\n\ngo 1.22\n"

GO_BASE = '''package hopdev

import (
	"path/filepath"
	"strings"
)

type Item struct {
	Label string
	Size  int
}

type Matcher struct {
	Codes []int
}

type Stage struct {
	When  *Matcher
	Steps []Item
}

type Pipeline struct {
	Stages []Stage
}

func Name(raw, prefix string) Item {
	label := strings.TrimPrefix(raw, prefix)
	label = filepath.ToSlash(label)
	other := strings.ToUpper(raw)
	_ = other
	return Item{Label: label, Size: len(raw)}
}

func Assemble(step Item) Pipeline {
	ok := Stage{
		When: &Matcher{
			Codes: []int{2},
		},
	}
	fallback := Stage{When: &Matcher{Codes: []int{5}}}
	ok.Steps = append(ok.Steps, step)
	var p Pipeline
	p.Stages = append(p.Stages, ok)
	_ = fallback
	return p
}

func Rename(it *Item, raw string) {
	clean := strings.TrimSpace(raw)
	it.Label = clean
}
'''

GO_HEAD = (GO_BASE
           .replace("\t_ = other\n", "\tlabel = other\n")
           .replace("\tfallback := Stage{When: &Matcher{Codes: []int{5}}}\n",
                    "\tok = Stage{When: &Matcher{Codes: []int{5}}}\n")
           .replace("\t_ = fallback\n", "\t_ = ok\n"))

PY_BASE = '''"""Hop verifier development module (not an evaluation fixture)."""


class Codec:
    def decode(self, blob, key):
        return blob


class Mirror:
    def decode(self, blob, key):
        return key


class Registry:
    ENTRIES = {}

    @classmethod
    def add(cls, entry):
        cls.ENTRIES[entry.name] = entry


class Plain:
    name = "plain"

    def check(self, data, sig):
        return sig == ""


class Signed:
    name = "signed"

    def check(self, data, sig):
        return False


class Unlisted:
    name = "unlisted"

    def check(self, data, sig):
        return True


for _entry in (Plain(), Signed()):
    Registry.add(_entry)


class Reader:
    def __init__(self):
        self._codec = Codec()
        self._mirror = Mirror()

    def read(self, blob, key):
        return self._codec.decode(blob, key)

    def reflect(self, blob, key):
        return self._mirror.decode(blob, key)

    def verify(self, kind, data, sig):
        chosen = Registry.ENTRIES[kind]
        return chosen.check(data, sig)


class Alpha:
    def handle(self, x):
        return x + 1


class Beta:
    def handle(self, x):
        return x * 2


class Gamma:
    def handle(self, x):
        return -x


HANDLERS = {"a": Alpha(), "b": Beta()}


def run(kind, x):
    handler = HANDLERS[kind]
    return handler.handle(x)
'''

PY_HEAD = (PY_BASE
           .replace("for _entry in (Plain(), Signed()):", "for _entry in (Signed(), Unlisted()):")
           .replace("self._codec = Codec()", "self._codec = Mirror()")
           .replace('HANDLERS = {"a": Alpha(), "b": Beta()}', 'HANDLERS = {"a": Alpha(), "b": Gamma()}'))


def git_repo(dest: Path, commits: list[tuple[str, dict[str, str]]], who: str) -> dict[str, str]:
    """A small repository with one tagged commit per entry; returns tag -> sha."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": who, "GIT_AUTHOR_EMAIL": f"{who}@example.invalid",
           "GIT_COMMITTER_NAME": who, "GIT_COMMITTER_EMAIL": f"{who}@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(dest), *args], env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "main")
    shas = {}
    for tag, files in commits:
        for name, text in files.items():
            (dest / name).write_text(text)
        git("add", "-A")
        git("commit", "-q", "--no-gpg-sign", "-m", tag)
        git("tag", tag)
        shas[tag] = git("rev-parse", "HEAD")
    return shas


def main() -> None:
    for text in (GO_BASE, GO_HEAD):
        assert text.count("\n") == GO_BASE.count("\n")
    for text in (PY_BASE, PY_HEAD):
        assert text.count("\n") == PY_BASE.count("\n")
    go = git_repo(ROOT / ".cache/fixtures/hopdev-go",
                  [("base", {"go.mod": GO_MOD, "flow.go": GO_BASE}), ("head", {"flow.go": GO_HEAD})],
                  "hopdev")
    py = git_repo(ROOT / ".cache/fixtures/hopdev-py",
                  [("base", {"dev.py": PY_BASE}), ("head", {"dev.py": PY_HEAD})], "hopdev")
    print(f"hopdev-go base {go['base']} head {go['head']}")
    print(f"hopdev-py base {py['base']} head {py['head']}")


if __name__ == "__main__":
    main()
