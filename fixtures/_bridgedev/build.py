"""Build the §14 bridge-verifier development modules (NOT evaluation fixtures).

    uv run python fixtures/_bridgedev/build.py   # -> .cache/fixtures/bridgedev-{go,py} (tag base)

PREREGISTRATION.md §14: the bridge verifiers were developed against these only. They share no
code with Authlib, Caddy or File Browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

GO_MOD = "module example.com/bridgedev\n\ngo 1.22\n"

GO = '''package bridgedev

import "strings"

type Entry struct {
	Name string
}

type Namer interface {
	Name(s string) string
}

type upper struct{}

func (upper) Name(s string) string { return strings.ToUpper(s) }

func clean(p string) string { return strings.TrimSpace(p) }

func label(prefix, raw string) string {
	name := strings.TrimPrefix(raw, prefix)
	return name
}

func join(sep string, parts ...string) string { return strings.Join(parts, sep) }

func Collect(raw []string, prefix string) []Entry {
	items := raw
	var out []Entry
	for _, item := range items {
		cleaned := clean(item)
		out = append(out, Entry{Name: label(prefix, cleaned)})
	}
	for i := range items {
		_ = i
	}
	other := []string{"x"}
	for _, o := range other {
		_ = o
	}
	return out
}

func Dispatch(n Namer, v string) string {
	w := strings.TrimSpace(v)
	return n.Name(w)
}

func Variadic(a, b string) string {
	x := strings.TrimSpace(a)
	return join("-", x, b)
}

func Kill(v string) string {
	t := v
	t = "const"
	return clean(t)
}

func Value(f func(string) string, v string) string {
	u := strings.TrimSpace(v)
	return f(u)
}
'''

PY = '''"""Bridge verifier development module (not an evaluation fixture)."""


def to_text(x):
    return str(x)


class Box:
    def open(self, key, blob):
        return blob


class Reader:
    def __init__(self):
        self._box = Box()

    def read(self, token, key):
        token = to_text(token)
        data = self._box.open(key, token)
        return data

    def skip(self, token, key):
        token = "fixed"
        return self._box.open(key, token)

    def other(self, token, key):
        name = to_text(key)
        return self._box.open(name, "x")
'''


def main() -> None:
    go = git_repo(ROOT / ".cache/fixtures/bridgedev-go", [("base", {"go.mod": GO_MOD, "bridge.go": GO})],
                  "bridgedev")
    py = git_repo(ROOT / ".cache/fixtures/bridgedev-py", [("base", {"bridge.py": PY})], "bridgedev")
    print(f"bridgedev-go base {go['base']}\nbridgedev-py base {py['base']}")


if __name__ == "__main__":
    main()
