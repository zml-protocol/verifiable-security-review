"""Build the Spike P pilot Go module (not an evaluation fixture) as a one-commit git repo.

    python fixtures/_pilot/build_goflow.py   # -> .cache/fixtures/pilot-goflow, tag `base`

It exercises the same relation types as the evaluation fixtures (field flow
through locals into a struct, object composition into nested collections)
without sharing any of their code.
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / ".cache" / "fixtures" / "pilot-goflow"

GO_MOD = "module example.com/goflow\n\ngo 1.22\n"
FLOW_GO = '''package goflow

import "strings"

type Entry struct {
	Name string
	Size int
}

type Handler struct {
	Match  []int
	Routes []Entry
}

type Proxy struct {
	HandleResponse []Handler
}

func Build(names []string) []Entry {
	var out []Entry
	for _, n := range names {
		out = append(out, collect(n)...)
	}
	return out
}

func collect(path string) []Entry {
	name := strings.TrimPrefix(path, "/")
	name = strings.ReplaceAll(name, "\\\\", "/")
	return []Entry{{Name: name}}
}

func Compose(extra Entry) Proxy {
	good := Handler{Match: []int{2}}
	good.Routes = append(good.Routes, extra)
	p := Proxy{}
	p.HandleResponse = append(p.HandleResponse, good)
	return p
}
'''


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST / "go.mod").write_text(GO_MOD)
    (DEST / "flow.go").write_text(FLOW_GO)
    env = {**os.environ, "GIT_AUTHOR_NAME": "pilot", "GIT_AUTHOR_EMAIL": "pilot@example.invalid",
           "GIT_COMMITTER_NAME": "pilot", "GIT_COMMITTER_EMAIL": "pilot@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                ["commit", "-q", "--no-gpg-sign", "-m", "pilot"], ["tag", "base"]):
        subprocess.run(["git", "-C", str(DEST), *cmd], env=env, check=True)
    print(subprocess.run(["git", "-C", str(DEST), "rev-parse", "base"],
                         capture_output=True, text=True, check=True).stdout.strip())


if __name__ == "__main__":
    main()
