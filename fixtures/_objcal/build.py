"""Build the same-object connector calibration module (held out; NOT an evaluation fixture).

    uv run python fixtures/_objcal/build.py   # -> .cache/fixtures/objcal-go (tag base)

PREREGISTRATION.md §12.1: written before the connector ran on it, frozen with the
connector, run once after the freeze. It shares no code with the development module or
with Authlib, Caddy or File Browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

GO_MOD = "module example.com/objcal\n\ngo 1.22\n"

GO = '''package objcal

type Inner struct {
	N int
}

type Box struct {
	In    Inner
	Count int
	Name  string
}

func (b Box) Label() string { return b.Name }

func (b *Box) Bump() { b.Count++ }

func id(b Box) Box { return b }

func Plain() Box {
	box := Box{Name: "x"}
	box.Count = 1
	label := box.Label()
	box.Name = label
	return box
}

func Siblings(c bool) Box {
	if c {
		box := Box{}
		box.Count = 1
		return box
	} else {
		box := Box{}
		box.Count = 2
		return box
	}
}

func Switch(k int) Box {
	box := Box{}
	switch k {
	case 1:
		box := Box{}
		box.Count = 1
		_ = box
	default:
		box.Count = 2
	}
	return box
}

func Loop(xs []int) Box {
	box := Box{}
	for _, x := range xs {
		box.Count = x
		box = Box{}
	}
	return box
}

func Branch(c bool) Box {
	box := Box{}
	if c {
		box.Count = 1
	} else {
		box = Box{Name: "y"}
	}
	box.Name = "z"
	return box
}

func Returned() (Box, Box) {
	box := Box{}
	other := id(box)
	other.Count = 1
	return box, other
}

func Alias() *Box {
	p := &Box{}
	q := p
	q.Count = 1
	return p
}

func Nested() Box {
	box := Box{}
	box.In.N = 1
	return box
}

func Goroutine() Box {
	box := Box{}
	done := make(chan bool)
	go func() { box.Count = 1; done <- true }()
	<-done
	return box
}

func Zero() Box {
	var box Box
	box.Count = 1
	return box
}

func PointerMethod() *Box {
	p := &Box{}
	p.Bump()
	p.Count = 2
	return p
}
'''


def main() -> None:
    shas = git_repo(ROOT / ".cache/fixtures/objcal-go", [("base", {"go.mod": GO_MOD, "cal.go": GO})],
                    "objcal")
    print(f"objcal-go base {shas['base']}")


if __name__ == "__main__":
    main()
