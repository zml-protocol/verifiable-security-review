"""Build the same-object connector development module (NOT an evaluation fixture).

    uv run python fixtures/_objdev/build.py   # -> .cache/fixtures/objdev-go (tag base)

PREREGISTRATION.md §12.1: the connector was developed against this module only. It shares
no code with Authlib, Caddy or File Browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

GO_MOD = "module example.com/objdev\n\ngo 1.22\n"

GO = '''package objdev

type T struct {
	F int
	G int
}

func make2() (T, error) { return T{}, nil }

func (t *T) Reset() { *t = T{} }

func Same() T {
	o := T{}
	o.F = 1
	o.G = 2
	return o
}

func Pointer() *T {
	p := &T{}
	p.F = 1
	return p
}

func Reassign() T {
	o := T{}
	o.F = 1
	o = T{}
	o.G = 2
	return o
}

func Shadow(c bool) T {
	o := T{}
	if c {
		o := T{}
		o.F = 1
		_ = o
	}
	o.G = 2
	return o
}

func Two() (T, T) {
	a := T{}
	b := T{}
	a.F = 1
	b.F = 2
	return a, b
}

func First() T {
	o := T{}
	return o
}

func Second() T {
	o := T{}
	o.F = 1
	return o
}

func Copy() (T, T) {
	o := T{}
	w := o
	w.F = 1
	return o, w
}

func Addressed() T {
	o := T{}
	p := &o
	o.F = 1
	_ = p
	return o
}

func Merge(c bool) T {
	o := T{}
	if c {
		o = T{}
	}
	o.F = 1
	return o
}

func Multi() T {
	o, err := make2()
	_ = err
	o.F = 1
	return o
}

func Method() T {
	o := T{}
	o.Reset()
	o.F = 1
	return o
}

func Closure() T {
	o := T{}
	func() { o.F = 1 }()
	return o
}
'''


def main() -> None:
    shas = git_repo(ROOT / ".cache/fixtures/objdev-go", [("base", {"go.mod": GO_MOD, "obj.go": GO})],
                    "objdev")
    print(f"objdev-go base {shas['base']}")


if __name__ == "__main__":
    main()
