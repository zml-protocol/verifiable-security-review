"""Build the §14 bridge-verifier calibration modules (held out; NOT evaluation fixtures).

    uv run python fixtures/_bridgecal/build.py   # -> .cache/fixtures/bridgecal-{go,py} (tag base)

PREREGISTRATION.md §14: written before any bridge verifier ran on it, frozen with the
verifiers, run once after the freeze. Shares no code with the development modules or with
Authlib, Caddy or File Browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

GO_MOD = "module example.com/bridgecal\n\ngo 1.22\n"

GO = '''package bridgecal

import (
	"path"
	"strings"
)

type Record struct {
	Key string
}

type Sink interface {
	Put(k string)
}

type memSink struct{ keys []string }

func (m *memSink) Put(k string) { m.keys = append(m.keys, k) }

func normalize(s string) string { return path.Clean(s) }

func tag(kind string, value string) string {
	joined := kind + ":" + value
	return joined
}

func pick(a, b string) string { return b }

func Load(names []string, kind string, sink Sink) []Record {
	var out []Record
	list := names
	for idx, n := range list {
		norm := normalize(n)
		t := tag(kind, norm)
		out = append(out, Record{Key: t})
		_ = idx
	}
	fixed := []string{"z"}
	for _, f := range fixed {
		sink.Put(f)
	}
	return out
}

func Swap(a, b string) string {
	return pick(a, b)
}

func Shadow(v string) string {
	w := v
	if len(w) > 3 {
		w := "short"
		return normalize(w)
	}
	return normalize(w)
}

func Closure(v string) string {
	apply := func(s string) string { return strings.ToUpper(s) }
	return apply(v)
}
'''

PY = '''"""Bridge verifier calibration module (held out; not an evaluation fixture)."""


def decode_text(raw):
    return raw.decode()


class Store:
    def save(self, name, payload):
        return name


class Service:
    def __init__(self):
        self.store = Store()

    def handle(self, request, user):
        body = decode_text(request)
        body = body.strip()
        saved = self.store.save(user, body)
        return saved

    def reset(self, request, user):
        request = None
        return self.store.save(user, request)

    def nested(self, request, user):
        def inner(request):
            return request
        return self.store.save(user, inner("x"))

    def kw(self, request, user):
        return self.store.save(name=user, payload=request)
'''


def main() -> None:
    go = git_repo(ROOT / ".cache/fixtures/bridgecal-go", [("base", {"go.mod": GO_MOD, "cal.go": GO})],
                  "bridgecal")
    py = git_repo(ROOT / ".cache/fixtures/bridgecal-py", [("base", {"cal.py": PY})], "bridgecal")
    print(f"bridgecal-go base {go['base']}\nbridgecal-py base {py['base']}")


if __name__ == "__main__":
    main()
