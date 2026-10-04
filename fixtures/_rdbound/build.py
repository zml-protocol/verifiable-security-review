"""Build the RD boundary-case modules (PREREGISTRATION.md §15.1; synthetic, NOT evaluation fixtures).

    uv run python fixtures/_rdbound/build.py

- rdbound-go, rdbound-py (tag base): one module per language with the relation boundary cases.
- rdscen-go, rdscen-py (tags vuln, fixed): small two-revision scenarios for the requirement-level
  definitions (entry, behavior, absent context, qualifier kinds).

Written before any RD candidate fixture was looked at. Shares no code with any fixture.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_hopdev"))

from build import ROOT, git_repo

REL_GO = '''package rdbound

import "strings"

type Route struct {
	Handler string
	Tags    []string
}

type Meta struct {
	Owner string
	Level int
}

type Table struct {
	Name   string
	Routes []Route
	Meta   *Meta
}

type Sink interface {
	Put(k string)
}

type memSink struct{ keys []string }

func (m *memSink) Put(k string) { m.keys = append(m.keys, k) }

func clean(s string) string { return strings.TrimSpace(s) }

func join(prefix string, parts ...string) string { return prefix + strings.Join(parts, ",") }

func split(s string) (string, error) { return s, nil }

// ---- object_composition

func Spread(t *Table, h string) {
	batch := []Route{}
	r := Route{Handler: h}
	batch = append(batch, r)
	t.Routes = append(t.Routes, batch...)
}

func Direct(t *Table, h string) {
	one := Route{Handler: h}
	t.Routes = append(t.Routes, one)
}

func Earlier(t *Table) {
	m := &Meta{Level: 1}
	holder := &Table{}
	holder.Meta = m
	t.Meta = holder.Meta
}

func Self() Table {
	x := Table{Name: "a"}
	item := Route{Handler: "h"}
	x.Routes = append(x.Routes, item)
	return x
}

func Alias(t *Table, owner string) {
	pm := &Meta{}
	p := pm
	p.Owner = owner
	t.Meta = pm
}

func Copy(t *Table, owner string) {
	v := Meta{}
	w := v
	w.Owner = owner
	t.Meta = &v
}

// ---- field_flow

func Flow(raw string, other string) Route {
	name := clean(raw)
	name2 := name
	tag := other
	tag = "fixed"
	label := func() string { return name }
	return Route{Handler: name2, Tags: []string{tag, label()}}
}

func Multi(s string) Route {
	head, rest, _ := strings.Cut(s, ":")
	return Route{Handler: rest, Tags: []string{head}}
}

// ---- guard_property

func Guarded(t *Table, h string) {
	cfg := Table{
		Name: "guard",
		Meta: &Meta{Level: 2},
	}
	cfg.Routes = append(cfg.Routes, Route{Handler: h})
	t.Meta = cfg.Meta
	cfg = Table{Name: "reset"}
	cfg.Name = h
	t.Name = cfg.Name
}

// ---- def_use

func Uses(in string, sink Sink) string {
	a := in
	b := a + "/x"
	a = "reset"
	c := strings.ToUpper(a)
	f := func() { sink.Put(b) }
	f()
	t := Table{Name: b}
	d := t.Name
	k, err := split(b)
	if err != nil {
		return ""
	}
	sink.Put(k)
	return c + d
}

// ---- argument_binding

type nopSink struct{}

func (nopSink) Put(k string) {}

func Bind(sink Sink, ms *memSink, x string) string {
	sink.Put(x)
	ms.Put(x)
	out := join("p", x, "q")
	return out + join(x)
}

func Use() string {
	return Bind(&memSink{}, &memSink{}, "z")
}

func shout(s string) string { return strings.ToUpper(s) + "!" }

func Apply(x string) string {
	apply := clean
	return apply(x)
}

// ---- range_element

func Ranges(names []string, t Table, m map[string]int) int {
	list := names
	n := 0
	for i := range list {
		n += i
	}
	for _, v := range list {
		n += len(v)
	}
	for _, r := range t.Routes {
		n += len(r.Handler)
	}
	for k, c := range m {
		n += len(k) + c
	}
	return n
}
'''

REL_PY = '''"""RD boundary module (synthetic; not an evaluation fixture)."""


class Store:
    def save(self, name, payload):
        return name


class AuditStore(Store):
    def save(self, name, payload):
        return payload


class Service:
    def __init__(self):
        self.store = AuditStore()

    def run(self, name, payload):
        return self.store.save(name, payload)


class Plain:
    def render(self, text):
        return text


class Upper:
    def render(self, text):
        return text.upper()


class Hidden:
    def render(self, text):
        return ""


RENDERERS = {"plain": Plain(), "upper": Upper()}


def render(kind, text):
    r = RENDERERS[kind]
    return r.render(text)


def handle(request, user, store):
    body = request.read()
    body = body.strip()
    items = [x for x in [body]]
    later = [body for _ in range(1)]
    fn = lambda: body  # noqa: E731
    saved = store.save(name=user, payload=body)
    user = None
    return [store.save(user, fn()), items, later, saved]
'''

S1_VULN = '''package scen

import "net/http"

type Account struct {
	Name    string
	IsAdmin bool
}

type Store struct{ items map[string]string }

func (s *Store) DeleteAll() { s.items = map[string]string{} }

var sessions = map[string]Account{}

func lookup(r *http.Request) Account {
	return sessions[r.Header.Get("Cookie")]
}

func HandleReset(w http.ResponseWriter, r *http.Request, s *Store) {
	u := lookup(r)
	w.Header().Set("X-Account", u.Name)
	s.DeleteAll()
	w.WriteHeader(http.StatusNoContent)
}
'''

S1_FIXED = S1_VULN.replace('''	w.Header().Set("X-Account", u.Name)
''', '''	w.Header().Set("X-Account", u.Name)
	if !u.IsAdmin {
		w.WriteHeader(http.StatusForbidden)
		return
	}
''')

S2_VULN = '''package scen

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

func HandleDownload(w http.ResponseWriter, r *http.Request, root string) {
	if os.Getenv("ALLOW_DOWNLOAD") != "1" {
		http.Error(w, "disabled", http.StatusForbidden)
		return
	}
	name := r.URL.Query().Get("file")
	clean := strings.TrimSpace(name)
	data, err := os.ReadFile(filepath.Join(root, clean))
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.Write(data)
}
'''

S2_FIXED = S2_VULN.replace('''	clean := strings.TrimSpace(name)
''', '''	clean := strings.TrimSpace(name)
	clean = filepath.Base(clean)
''')

S3_VULN = '''package scen

import (
	"database/sql"
	"net/http"
)

type Policy struct {
	Mode  string
	Label string
}

func HandleSearch(w http.ResponseWriter, r *http.Request, db *sql.DB, p Policy) {
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	if p.Mode != "raw" {
		http.Error(w, "unsupported", http.StatusBadRequest)
		return
	}
	if p.Label != "" {
		w.Header().Set("X-Policy", p.Label)
	}
	term := r.FormValue("q")
	rows, err := db.Query("SELECT name FROM items WHERE name = '" + term + "'")
	if err != nil {
		http.Error(w, "error", http.StatusInternalServerError)
		return
	}
	defer rows.Close()
	w.WriteHeader(http.StatusOK)
}
'''

S3_FIXED = S3_VULN.replace(
    '''	rows, err := db.Query("SELECT name FROM items WHERE name = '" + term + "'")''',
    '''	rows, err := db.Query("SELECT name FROM items WHERE name = ?", term)''')

S5_VULN = '''package scen

import (
	"fmt"
	"net/http"
)

type Settings struct {
	APIToken string
	Version  string
}

func HandleStatus(w http.ResponseWriter, r *http.Request, st Settings) {
	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "ok %s\\n", r.URL.Path)
	fmt.Fprintf(w, "token=%s\\n", st.APIToken)
	fmt.Fprintf(w, "version=%s\\n", st.Version)
}
'''

S5_FIXED = S5_VULN.replace('''	fmt.Fprintf(w, "token=%s\\n", st.APIToken)
''', "")

S4_VULN = '''"""RD boundary scenario (synthetic)."""
import hashlib
import hmac


class NoneAlg:
    def verify(self, msg, sig, key):
        return sig == b""


class HmacAlg:
    def verify(self, msg, sig, key):
        return hmac.compare_digest(sig, hmac.new(key, msg, hashlib.sha256).digest())


ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}


def check(header, msg, sig, key):
    name = header["alg"]
    alg = ALGS[name]
    return alg.verify(msg, sig, key)
'''

S4_FIXED = S4_VULN.replace('ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}', 'ALGS = {"HS256": HmacAlg()}')

S6_VULN = '''"""RD boundary scenario (synthetic)."""
import os


def safe_path(base, user_path):
    full = os.path.normpath(os.path.join(base, user_path))
    if not full.startswith(base):
        raise ValueError("outside")
    return full
'''

S6_FIXED = S6_VULN.replace("    if not full.startswith(base):",
                           "    if os.path.commonpath([full, base]) != base:")

S7_VULN = '''package scen

import (
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

func HandleFile(w http.ResponseWriter, r *http.Request, root string) {
	raw := r.URL.Query().Get("p")
	if strings.Contains(raw, "..") {
		http.Error(w, "bad path", http.StatusBadRequest)
		return
	}
	name, err := url.QueryUnescape(raw)
	if err != nil {
		http.Error(w, "bad escape", http.StatusBadRequest)
		return
	}
	data, err := os.ReadFile(filepath.Join(root, name))
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.Write(data)
}
'''

S7_FIXED = '''package scen

import (
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

func HandleFile(w http.ResponseWriter, r *http.Request, root string) {
	raw := r.URL.Query().Get("p")
	name, err := url.QueryUnescape(raw)
	if err != nil {
		http.Error(w, "bad escape", http.StatusBadRequest)
		return
	}
	if strings.Contains(name, "..") {
		http.Error(w, "bad path", http.StatusBadRequest)
		return
	}
	data, err := os.ReadFile(filepath.Join(root, name))
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.Write(data)
}
'''

S8_VULN = '''package scen

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

type Uploader struct {
	Name     string
	Verified bool
}

func HandleUpload(w http.ResponseWriter, r *http.Request, u Uploader, root string, data []byte) {
	key := r.URL.Query().Get("key")
	if strings.HasPrefix(key, "/") {
		http.Error(w, "bad key", http.StatusBadRequest)
		return
	}
	err := os.WriteFile(filepath.Join(root, key), data, 0o600)
	if err != nil {
		http.Error(w, "write failed", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusCreated)
}
'''

S8_FIXED = S8_VULN.replace('''	key := r.URL.Query().Get("key")
	if strings.HasPrefix(key, "/") {
''', '''	if !u.Verified {
		http.Error(w, "unverified", http.StatusForbidden)
		return
	}
	key := r.URL.Query().Get("key")
	if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {
''')

S9_VULN = '''package scen

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

func HandleExport(w http.ResponseWriter, r *http.Request, root string, data []byte) {
	name := r.URL.Query().Get("name")
	if strings.HasPrefix(name, "/") {
		http.Error(w, "bad name", http.StatusBadRequest)
		return
	}
	err := os.WriteFile(filepath.Join(root, name), data, 0o600)
	if err != nil {
		http.Error(w, "write failed", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusCreated)
}
'''

S9_FIXED = S9_VULN.replace('''	name := r.URL.Query().Get("name")
	if strings.HasPrefix(name, "/") {
''', '''	name := r.URL.Query().Get("name")
	if strings.Contains(name, "..") {
		http.Error(w, "dot segments", http.StatusBadRequest)
		return
	}
	if strings.HasPrefix(name, "/") || strings.Contains(name, "..") {
''')

GO_MOD = "module example.com/{name}\n\ngo 1.22\n"

SCEN_GO = {"vuln": {"s1.go": S1_VULN, "s2.go": S2_VULN, "s3.go": S3_VULN, "s5.go": S5_VULN,
                    "s7.go": S7_VULN, "s8.go": S8_VULN, "s9.go": S9_VULN},
           "fixed": {"s1.go": S1_FIXED, "s2.go": S2_FIXED, "s3.go": S3_FIXED, "s5.go": S5_FIXED,
                     "s7.go": S7_FIXED, "s8.go": S8_FIXED, "s9.go": S9_FIXED}}
SCEN_PY = {"vuln": {"s4.py": S4_VULN, "s6.py": S6_VULN},
           "fixed": {"s4.py": S4_FIXED, "s6.py": S6_FIXED}}


def main() -> None:
    for rev in (SCEN_GO, SCEN_PY):
        for name in rev["vuln"]:
            assert rev["vuln"][name] != rev["fixed"][name], name
    out = {}
    out["rdbound-go"] = git_repo(ROOT / ".cache/fixtures/rdbound-go",
                                 [("base", {"go.mod": GO_MOD.format(name="rdbound"), "bound.go": REL_GO})],
                                 "rdbound")
    out["rdbound-py"] = git_repo(ROOT / ".cache/fixtures/rdbound-py", [("base", {"bound.py": REL_PY})],
                                 "rdbound")
    out["rdscen-go"] = git_repo(ROOT / ".cache/fixtures/rdscen-go",
                                [("vuln", {"go.mod": GO_MOD.format(name="scen"), **SCEN_GO["vuln"]}),
                                 ("fixed", SCEN_GO["fixed"])], "rdscen")
    out["rdscen-py"] = git_repo(ROOT / ".cache/fixtures/rdscen-py",
                                [("vuln", SCEN_PY["vuln"]), ("fixed", SCEN_PY["fixed"])], "rdscen")
    for repo, tags in out.items():
        for tag, sha in tags.items():
            print(f"{repo} {tag} {sha}")


if __name__ == "__main__":
    main()
