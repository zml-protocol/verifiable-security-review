"""Build the hop-verifier calibration modules (held out; NOT evaluation fixtures).

    uv run python fixtures/_hopcal/build.py   # -> .cache/fixtures/hopcal-{go,py}, tags base/head

PREREGISTRATION.md §10: written before any verifier ran on it and frozen with
the verifiers; the verifiers run on it once, after the freeze. It shares no
code with the development modules (fixtures/_hopdev) or with Authlib, Caddy
or File Browser. Each head commit replaces lines without moving any other
line, as in the development modules.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

GO_MOD = "module example.com/hopcal\n\ngo 1.22\n"

GO_BASE = '''package hopcal

import "strings"

type Header struct {
	Key   string
	Value string
}

type Rule struct {
	Methods []string
	Headers []Header
}

type Router struct {
	Rules []Rule
}

func MakeHeader(name, raw string) Header {
	key := strings.ToUpper(name)
	value := strings.TrimSpace(raw)
	value = strings.ToLower(value)
	return Header{Key: key, Value: value}
}

func Configure(h Header) *Router {
	get := Rule{
		Methods: []string{"GET"},
	}
	post := Rule{Methods: []string{"POST"}}
	get.Headers = append(get.Headers, h)
	r := &Router{}
	r.Rules = append(r.Rules, get)
	r.Rules = append(r.Rules, post)
	return r
}

func Tag(h *Header, raw string) {
	v := strings.TrimSpace(raw)
	h.Value = v
}
'''

GO_HEAD = (GO_BASE
           .replace("\tvalue = strings.ToLower(value)\n", "\tvalue = strings.ToLower(key)\n")
           .replace("\tpost := Rule{Methods: []string{\"POST\"}}\n",
                    "\tget = Rule{Methods: []string{\"POST\"}}\n")
           .replace("\tr.Rules = append(r.Rules, post)\n", "\tr.Rules = append(r.Rules, get)\n"))

PY_BASE = '''"""Hop verifier calibration module (held out; not an evaluation fixture)."""


class Store:
    def fetch(self, key):
        return key


class Cache:
    def fetch(self, key):
        return None


class Service:
    def __init__(self):
        self.backend = Store()
        self.cache = Cache()

    def lookup(self, key):
        return self.backend.fetch(key)

    def peek(self, key):
        return self.cache.fetch(key)


class Upper:
    def apply(self, text):
        return text.upper()


class Lower:
    def apply(self, text):
        return text.lower()


class Strip:
    def apply(self, text):
        return text.strip()


TRANSFORMS = {}


def install(name, transform):
    TRANSFORMS[name] = transform


install("up", Upper())
install("low", Lower())


def transform(name, text):
    t = TRANSFORMS.get(name)
    return t.apply(text)


PIPELINE = [Strip()]


def first(text):
    return PIPELINE[0].apply(text)


class Formats:
    TABLE = {}

    @classmethod
    def register(cls, codec):
        cls.TABLE[codec.tag] = codec

    def render(self, tag, value):
        codec = self.TABLE[tag]
        return codec.encode(value)


class Parsers:
    TABLE = {}

    @classmethod
    def register(cls, codec):
        cls.TABLE[codec.tag] = codec


class Json:
    tag = "json"

    def encode(self, value):
        return "j"


class Yaml:
    tag = "yaml"

    def encode(self, value):
        return "y"


Formats.register(Json())
Parsers.register(Yaml())
'''

PY_HEAD = (PY_BASE
           .replace("self.backend = Store()", "self.backend = Cache()")
           .replace('install("low", Lower())', 'install("low", Strip())')
           .replace("Parsers.register(Yaml())", "Formats.register(Yaml())"))


def main() -> None:
    for base, head in ((GO_BASE, GO_HEAD), (PY_BASE, PY_HEAD)):
        assert base != head and base.count("\n") == head.count("\n")
    go = git_repo(ROOT / ".cache/fixtures/hopcal-go",
                  [("base", {"go.mod": GO_MOD, "cal.go": GO_BASE}), ("head", {"cal.go": GO_HEAD})],
                  "hopcal")
    py = git_repo(ROOT / ".cache/fixtures/hopcal-py",
                  [("base", {"cal.py": PY_BASE}), ("head", {"cal.py": PY_HEAD})], "hopcal")
    print(f"hopcal-go base {go['base']} head {go['head']}")
    print(f"hopcal-py base {py['base']} head {py['head']}")


if __name__ == "__main__":
    main()
