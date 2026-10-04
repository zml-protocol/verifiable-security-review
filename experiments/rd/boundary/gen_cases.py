"""Write the RD boundary cases and the author's labels (PREREGISTRATION.md §15.1).

    uv run python fixtures/_rdbound/build.py
    uv run python experiments/rd/boundary/gen_cases.py

Anchors are located from the module text (a unique line containing the expression), never typed
by hand. Cases (what adjudicators see) and labels (the author's, never shown to them) go to
separate files. Every label names the definition rule it tests (experiments/rd/definitions.yaml).
"""

from __future__ import annotations

import importlib.util
import random
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("rdbound_build", ROOT / "fixtures/_rdbound/build.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def sha(repo: str, tag: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT / ".cache/fixtures" / repo), "rev-parse", tag],
                          capture_output=True, text=True, check=True).stdout.strip()


def at(text: str, file: str, expr: str, line_has: str | None = None, whole: bool = False) -> dict:
    """The anchor of `expr` on the one line containing it (and `line_has`, when given); with
    `whole`, on the one line that is exactly `expr`."""
    lines = [i for i, line in enumerate(text.splitlines(), 1)
             if (line.strip() == expr if whole else expr in line)
             and (line_has is None or line_has in line)]
    assert len(lines) == 1, (file, expr, line_has, lines)
    return {"file": file, "start_line": lines[0], "end_line": lines[0], "expression": expr}


# ---- relation cases ---------------------------------------------------------------------

def relation_cases():
    go = lambda expr, has=None: at(B.REL_GO, "bound.go", expr, has)
    py = lambda expr, has=None: at(B.REL_PY, "bound.py", expr, has)
    G, P = "rdbound-go", "rdbound-py"
    T, F = True, False
    cases = [
        # object_composition
        ("oc-spread", G, "object_composition", go("batch = append(batch, r)"),
         go("t.Routes = append(t.Routes, batch...)"), T, "OC-3", "the spread container's defining statement: one step"),
        ("oc-initial-version", G, "object_composition", go("batch := []Route{}"),
         go("t.Routes = append(t.Routes, batch...)"), F, "OC-4", "the spread version of batch is defined by the later append"),
        ("oc-element-via-container", G, "object_composition", go("r := Route{Handler: h}"),
         go("t.Routes = append(t.Routes, batch...)"), F, "OC-3", "the element reaches the field only through the local container: two steps"),
        ("oc-direct-argument", G, "object_composition", go("one := Route{Handler: h}"),
         go("t.Routes = append(t.Routes, one)"), T, "OC-1", "an appended argument"),
        ("oc-earlier-store", G, "object_composition", go("m := &Meta{Level: 1}"),
         go("t.Meta = holder.Meta"), F, "OC-5", "m reaches the stored value only by being read back from holder.Meta"),
        ("oc-the-earlier-store-itself", G, "object_composition", go("m := &Meta{Level: 1}"),
         go("holder.Meta = m"), T, "OC-1", "m is the stored value"),
        ("oc-container", G, "object_composition", go('x := Table{Name: "a"}'),
         go("x.Routes = append(x.Routes, item)"), F, "OC-6", "x is the container, not a stored value"),
        ("oc-pointer-alias", G, "object_composition", go("p.Owner = owner"),
         go("t.Meta = pm"), T, "OC-7", "p and pm hold the same pointer: the modified object is stored"),
        ("oc-value-copy", G, "object_composition", go("w.Owner = owner"),
         go("t.Meta = &v"), F, "OC-7", "w is a copy of v; the stored object v was not modified"),
        # field_flow
        ("ff-through-local", G, "field_flow", go("name := clean(raw)"),
         go("Handler: name2", "return Route{Handler: name2"), T, "FF-4", "name reaches name2 by assignment"),
        ("ff-overwritten", G, "field_flow", go("tag := other"),
         go("Tags: []string{tag, label()}"), F, "FF-2", "tag is overwritten before the literal"),
        ("ff-closure", G, "field_flow", go("name := clean(raw)"),
         go("Tags: []string{tag, label()}"), F, "FF-3", "name reaches the field only through the closure"),
        ("ff-multi-definition", G, "field_flow", go('head, rest, _ := strings.Cut(s, ":")'),
         go("Handler: rest"), T, "FF-1", "rest is one of the variables the statement defines"),
        # guard_property
        ("gp-nested-field", G, "guard_property", go("Level: 2"),
         go("cfg.Routes = append(cfg.Routes, Route{Handler: h})"), T, "GP-1", "a keyed field inside &Meta{...} of cfg's initializer"),
        ("gp-redefined", G, "guard_property", go("Level: 2"),
         go("cfg.Name = h"), F, "GP-2", "cfg is redefined before this store"),
        ("gp-sibling", G, "guard_property", go('Name: "guard"'),
         go("cfg.Routes = append(cfg.Routes, Route{Handler: h})"), T, "GP-3", "structural: a sibling field holds too"),
        # def_use (Go)
        ("du-through-local", G, "def_use", go("in string", "func Uses"), go('b := a + "/x"'),
         T, "DU-1", "b reads a, which holds the parameter's value"),
        ("du-overwritten", G, "def_use", go("a := in"), go("c := strings.ToUpper(a)"),
         F, "DU-2", "a is overwritten before"),
        ("du-closure", G, "def_use", go('b := a + "/x"'), go("b) }"),
         F, "DU-3", "the read is inside a function literal"),
        ("du-selector-base", G, "def_use", go("t := Table{Name: b}"), go("d := t.Name"),
         T, "DU-4", "t is read as a selector base"),
        ("du-multi-definition", G, "def_use", go("k, err := split(b)"), go("k)", "sink.Put(k)"),
         T, "DU-5", "k is one of the variables the statement defines"),
        ("du-definition-to-definition", G, "def_use", go('b := a + "/x"'), go("k, err := split(b)"),
         T, "DU-1", "the right-hand side reads b"),
        # argument_binding
        ("ab-interface", G, "argument_binding", go("x)", "sink.Put(x)"), go("k string", "func (m *memSink) Put"),
         T, "AB-1", "Use passes a *memSink as sink: the interface call can run its Put"),
        ("ab-interface-unreachable", G, "argument_binding", go("x)", "sink.Put(x)"),
         go("k string", "func (nopSink) Put"), F, "AB-1",
         "nopSink implements Sink, but no nopSink value can reach sink (unexported, never built)"),
        ("ab-function-value", G, "argument_binding", go("x)", "apply(x)"), go("s string", "func clean"),
         T, "AB-1", "apply holds clean"),
        ("ab-function-value-other", G, "argument_binding", go("x)", "apply(x)"), go("s string", "func shout"),
         F, "AB-1", "shout has the same signature but is never assigned to apply"),
        ("ab-static", G, "argument_binding", go("x)", "ms.Put(x)"), go("k string", "func (m *memSink) Put"),
         T, "AB-4", "argument 0 of a static method call"),
        ("ab-variadic-tail", G, "argument_binding", go('x, "q")'), go("parts ...string"),
         F, "AB-2", "x goes into the variadic tail"),
        ("ab-first-argument", G, "argument_binding", go("x)", "join(x)"), go("prefix string"),
         T, "AB-4", "argument 0 binds prefix"),
        ("ab-receiver", G, "argument_binding", go("ms.Put(x)"), go("m *memSink"),
         F, "AB-3", "the receiver is not an argument"),
        # range_element
        ("re-copy", G, "range_element", go("names []string"), go("v := range list"),
         T, "RE-2", "list holds names"),
        ("re-local", G, "range_element", go("list := names"), go("v := range list"),
         T, "RE-2", "ranging over the defined value"),
        ("re-index", G, "range_element", go("list := names"), go("i := range list"),
         F, "RE-1", "a one-variable range binds the index"),
        ("re-field", G, "range_element", go("t Table"), go("r := range t.Routes"),
         F, "RE-3", "ranges over a field of t"),
        ("re-map-value", G, "range_element", go("m map[string]int"), go("c := range m"),
         T, "RE-4", "map values are elements"),
        # def_use (Python)
        ("pd-receiver-base", P, "def_use", py("request, user, store"), py("body = request.read()"),
         T, "DU-4", "request is read as the call receiver"),
        ("pd-overwritten", P, "def_use", py("body = request.read()"),
         py("saved = store.save(name=user, payload=body)"), F, "DU-2", "body is reassigned before"),
        ("pd-keyword", P, "def_use", py("body = body.strip()"),
         py("store.save(name=user, payload=body)"), T, "DU-1", "a keyword argument reads body"),
        ("pd-outer-iterable", P, "def_use", py("body = body.strip()"),
         py("items = [x for x in [body]]"), T, "DU-3", "the outermost iterable is evaluated in the function"),
        ("pd-comprehension-body", P, "def_use", py("body = body.strip()"),
         py("later = [body for _ in range(1)]"), F, "DU-3", "the read is in the comprehension body"),
        ("pd-reassigned-parameter", P, "def_use", py("user, store", "def handle"),
         py("store.save(user, fn())"), F, "DU-2", "user is reassigned to None before"),
        ("pd-lambda", P, "def_use", py("body = body.strip()"), py("store.save(user, fn())"),
         F, "DU-3", "body is read only inside the lambda"),
        ("pd-parameter-keyword", P, "def_use", py("user, store", "def handle"),
         py("saved = store.save(name=user, payload=body)"), T, "DU-1", "the keyword argument name=user"),
        # call_typed_attribute
        ("ct-override", P, "call_typed_attribute", py("self.store.save(name, payload)"),
         py("return payload"), T, "CT-1", "self.store only holds an AuditStore"),
        ("ct-overridden-base", P, "call_typed_attribute", py("self.store.save(name, payload)"),
         py("return name"), F, "CT-1", "AuditStore overrides save; Store.save cannot run"),
        # registry_dispatch
        ("rd-registered", P, "registry_dispatch", py("r.render(text)"), py("return text.upper()"),
         T, "RD-1", "Upper is registered"),
        ("rd-registered-plain", P, "registry_dispatch", py("r.render(text)"), at(B.REL_PY, "bound.py", "return text", whole=True),
         T, "RD-1", "Plain is registered"),
        ("rd-unregistered", P, "registry_dispatch", py("r.render(text)"), py('return ""'),
         F, "RD-1", "Hidden is never registered"),
    ]
    fixtures = {
        G: {"language": "go", "repo": ".cache/fixtures/rdbound-go", "commits": {"base": sha("rdbound-go", "base")}},
        P: {"language": "python", "repo": ".cache/fixtures/rdbound-py", "commits": {"base": sha("rdbound-py", "base")}},
    }
    hops, labels = [], {}
    for cid, fx, rel, a, b, label, rule, reason in cases:
        hops.append({"id": cid, "fixture": fx, "revision": "base", "relation": rel, "from": a, "to": b})
        labels[cid] = {"label": label, "rule": rule, "reason": reason}
    return {"set": "rd-boundary-relations", "fixtures": fixtures, "hops": hops}, labels


# ---- requirement scenarios --------------------------------------------------------------

def present(anchor):
    return {"state": "present", "anchor": anchor}


def absent(context):
    return {"state": "absent", "context": context}


def requirement_cases():
    def g(f, rev):
        return lambda expr, has=None: at(B.SCEN_GO[rev][f], f, expr, has)

    def p(f, rev):
        return lambda expr, has=None: at(B.SCEN_PY[rev][f], f, expr, has)

    both = lambda fn, f, expr, has=None: {r: present(fn(f, r)(expr, has)) for r in ("vuln", "fixed")}
    items, labels = [], {}

    def item(sid, iid, role, slots, label, rule, reason, kind=None, semantic=None):
        it = {"id": iid, "scenario": sid, "role": role}
        if kind:
            it["kind"] = kind
        if semantic:
            it["semantic"] = semantic
        it["slots"] = slots
        items.append(it)
        labels[iid] = {"label": label, "rule": rule, "reason": reason}

    R, N = "REQUIRED", "NOT_REQUIRED"
    # s1: missing authorization; the fix adds a check
    f = "s1.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    item("s1", "s1-entry-request", "entry", {"entry": both(g, f, "r *http.Request", "func HandleReset")},
         R, "EN-1", "the claim concerns the request as a whole")
    item("s1", "s1-entry-derived", "entry", {"entry": both(g, f, "u := lookup(r)")},
         N, "EN-3", "u is derived from the request")
    item("s1", "s1-behavior-check", "behavior",
         {"behavior": {"vuln": absent(v("s.DeleteAll()", "\ts.DeleteAll()")), "fixed": present(x("if !u.IsAdmin {"))}},
         R, "BE-1", "the fix adds the check; absent before, context = the statement after the insertion point")
    item("s1", "s1-behavior-wrong-context", "behavior",
         {"behavior": {"vuln": absent(v('w.Header().Set("X-Account", u.Name)')), "fixed": present(x("if !u.IsAdmin {"))}},
         N, "AC-3", "the context is the statement after the insertion point, not before it")
    item("s1", "s1-behavior-sink", "behavior", {"behavior": both(g, f, "s.DeleteAll()", "\ts.DeleteAll()")},
         N, "BE-1", "the fix adds a check: the behavior is the check, not the sink")
    item("s1", "s1-guard-is-behavior", "qualifier",
         {"subject": both(g, f, "u := lookup(r)"),
          "predicate": {"vuln": absent(v("s.DeleteAll()", "\ts.DeleteAll()")), "fixed": present(x("if !u.IsAdmin {"))}},
         N, "QU-2", "the added check is the behavior; not also a qualifier",
         kind="guard", semantic={"expected": "must_not_hold"})
    # s2: path traversal; the fix adds a transform; a config gate
    f = "s2.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    read = 'data, err := os.ReadFile(filepath.Join(root, clean))'
    item("s2", "s2-entry-extracted", "entry", {"entry": both(g, f, 'name := r.URL.Query().Get("file")')},
         R, "EN-2", "the first definition extracting the query parameter")
    item("s2", "s2-entry-request", "entry", {"entry": both(g, f, "r *http.Request", "func HandleDownload")},
         N, "EN-2", "the input is one part of the request")
    item("s2", "s2-entry-derived", "entry", {"entry": both(g, f, "clean := strings.TrimSpace(name)")},
         N, "EN-3", "derived after the first extraction")
    item("s2", "s2-behavior-transform", "behavior",
         {"behavior": {"vuln": absent(v(read)), "fixed": present(x("clean = filepath.Base(clean)"))}},
         R, "BE-1", "the fix adds the transform; context = the statement after the insertion point")
    item("s2", "s2-behavior-sink", "behavior", {"behavior": both(g, f, read)},
         N, "BE-1", "the fix adds a transform: the behavior is the transform")
    gate = 'if os.Getenv("ALLOW_DOWNLOAD") != "1" {'
    item("s2", "s2-config-equals", "qualifier",
         {"subject": both(g, f, gate), "config": both(g, f, 'os.Getenv("ALLOW_DOWNLOAD")')},
         R, "CF-1", "re-derived under v2: every admissible execution needs ALLOW_DOWNLOAD == \"1\" (the "
         "environment is otherwise free)",
         kind="config", semantic={"expected_condition": {"op": "equals", "value": "1"}})
    item("s2", "s2-config-set", "qualifier",
         {"subject": both(g, f, gate), "config": both(g, f, 'os.Getenv("ALLOW_DOWNLOAD")')},
         N, "CF-1", "re-derived under v2: `set` holds in every admissible execution, but CF-1 asks for the "
         "condition the behavior needs, equals \"1\"",
         kind="config", semantic={"expected_condition": {"op": "set"}})
    item("s2", "s2-transform-irrelevant", "qualifier",
         {"subject": both(g, f, 'name := r.URL.Query().Get("file")'),
          "transform": both(g, f, "clean := strings.TrimSpace(name)")},
         N, "QU-1", "trimming whitespace does not decide traversal",
         kind="transform", semantic={"expected": "must_be_present"})
    item("s2", "s2-transform-is-behavior", "qualifier",
         {"subject": both(g, f, "clean := strings.TrimSpace(name)"),
          "transform": {"vuln": absent(v(read)), "fixed": present(x("clean = filepath.Base(clean)"))}},
         N, "QU-2", "the added transform is the behavior",
         kind="transform", semantic={"expected": "must_be_absent"})
    # s3: SQL injection; the fix changes the sink; guards around it
    f = "s3.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    item("s3", "s3-entry-extracted", "entry", {"entry": both(g, f, 'term := r.FormValue("q")')},
         R, "EN-2", "the first extraction of the form value")
    item("s3", "s3-behavior-sink", "behavior",
         {"behavior": {"vuln": present(v("rows, err := db.Query(")), "fixed": present(x("rows, err := db.Query("))}},
         R, "BE-2", "the fix changes the dangerous operation itself")
    mode = 'if p.Mode != "raw" {'
    item("s3", "s3-guard-mode", "qualifier",
         {"subject": both(g, f, "p Policy"), "predicate": both(g, f, mode)},
         R, "GU-1", "the query runs only when the written condition is false",
         kind="guard", semantic={"expected": "must_not_hold"})
    item("s3", "s3-guard-mode-polarity", "qualifier",
         {"subject": both(g, f, "p Policy"), "predicate": both(g, f, mode)},
         N, "GU-1", "wrong polarity", kind="guard", semantic={"expected": "must_hold"})
    item("s3", "s3-guard-method", "qualifier",
         {"subject": both(g, f, "r *http.Request", "func HandleSearch"),
          "predicate": both(g, f, "if r.Method != http.MethodPost {")},
         N, "QU-3", "the attacker chooses the method", kind="guard", semantic={"expected": "must_not_hold"})
    item("s3", "s3-guard-sibling", "qualifier",
         {"subject": both(g, f, "p Policy"), "predicate": both(g, f, 'if p.Label != "" {')},
         N, "QU-1", "the label does not decide whether the query runs",
         kind="guard", semantic={"expected": "must_hold"})
    # s5: information exposure; the fix removes the sink
    f = "s5.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    token = 'fmt.Fprintf(w, "token=%s\\n", st.APIToken)'
    version = 'fmt.Fprintf(w, "version=%s\\n", st.Version)'
    ok = 'fmt.Fprintf(w, "ok %s\\n", r.URL.Path)'
    item("s5", "s5-entry-request", "entry", {"entry": both(g, f, "r *http.Request", "func HandleStatus")},
         R, "EN-1", "an exposure claim concerns the request as a whole")
    item("s5", "s5-behavior-removed", "behavior",
         {"behavior": {"vuln": present(v(token)), "fixed": absent(x(version))}},
         R, "AC-3", "removed by the fix; context = the statement after the removal point")
    item("s5", "s5-behavior-wrong-context", "behavior",
         {"behavior": {"vuln": present(v(token)), "fixed": absent(x(ok))}},
         N, "AC-3", "the context is the statement after the removal point, not before it")
    item("s5", "s5-behavior-wrong-state", "behavior",
         {"behavior": {"vuln": present(v(token)), "fixed": present(x(version))}},
         N, "ST-1", "the behavior does not exist at the fixed revision")
    # s4: signature bypass through a registry; the fix unregisters the none algorithm
    f = "s4.py"
    v, x = p(f, "vuln"), p(f, "fixed")
    item("s4", "s4-entry-extracted", "entry", {"entry": both(p, f, 'name = header["alg"]')},
         R, "EN-2", "the first extraction of the header field")
    item("s4", "s4-entry-header", "entry", {"entry": both(p, f, "header, msg, sig, key")},
         N, "EN-2", "the input is one key of the header")
    item("s4", "s4-behavior-sink", "behavior", {"behavior": both(p, f, 'return sig == b""')},
         R, "BE-2", "the fix changes a registry off the path: the behavior is the accepting statement")
    item("s4", "s4-behavior-registry", "behavior",
         {"behavior": {"vuln": present(v('ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}')),
                       "fixed": present(x('ALGS = {"HS256": HmacAlg()}'))}},
         N, "BE-2", "the registry is not a check or transform on the path")

    def verify_def(rev, cls):
        text = B.SCEN_PY[rev][f].splitlines()
        start = next(i for i, line in enumerate(text, 1) if line.startswith(f"class {cls}"))
        line = next(i for i in range(start, len(text) + 1) if "def verify(self, msg, sig, key):" in text[i - 1])
        return {"file": f, "start_line": line, "end_line": line, "expression": "def verify(self, msg, sig, key):"}

    call = both(p, f, "alg.verify(msg, sig, key)")
    item("s4", "s4-dispatch-none", "qualifier",
         {"call": call, "target": {r: present(verify_def(r, "NoneAlg")) for r in ("vuln", "fixed")}},
         R, "QU-1", "re-derived under v2: every admissible execution that bypasses the check dispatches to "
         "NoneAlg.verify (the attacker does not hold the key)",
         kind="dispatch_target")
    item("s4", "s4-dispatch-hmac", "qualifier",
         {"call": call, "target": {r: present(verify_def(r, "HmacAlg")) for r in ("vuln", "fixed")}},
         N, "QU-1", "re-derived under v2: no admissible execution needs HmacAlg.verify",
         kind="dispatch_target")
    # s6: path check; the fix changes the check
    f = "s6.py"
    v, x = p(f, "vuln"), p(f, "fixed")
    item("s6", "s6-entry-parameter", "entry", {"entry": both(p, f, "user_path", "def safe_path")},
         R, "EN-1", "the parameter holds exactly the input")
    item("s6", "s6-entry-derived", "entry",
         {"entry": both(p, f, "full = os.path.normpath(os.path.join(base, user_path))")},
         N, "EN-3", "derived from the input")
    item("s6", "s6-behavior-check", "behavior",
         {"behavior": {"vuln": present(v("if not full.startswith(base):")),
                       "fixed": present(x("if os.path.commonpath([full, base]) != base:"))}},
         R, "BE-1", "the fix changes the check")
    item("s6", "s6-behavior-return", "behavior", {"behavior": both(p, f, "return full")},
         N, "BE-1", "the fix changes the check: the behavior is the check")
    item("s6", "s6-transform-normalize", "qualifier",
         {"subject": both(p, f, "user_path", "def safe_path"),
          "transform": both(p, f, "full = os.path.normpath(os.path.join(base, user_path))")},
         N, "QU-1", "the prefix check is bypassed with or without normalization",
         kind="transform", semantic={"expected": "must_be_present"})

    # s7: double decoding; the fix moves the check after the decode; the decode is required
    f = "s7.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    decode = "name, err := url.QueryUnescape(raw)"
    item("s7", "s7-entry-extracted", "entry", {"entry": both(g, f, 'raw := r.URL.Query().Get("p")')},
         R, "EN-2", "the first extraction of the query parameter")
    item("s7", "s7-behavior-check", "behavior",
         {"behavior": {"vuln": present(v('if strings.Contains(raw, "..") {')),
                       "fixed": present(x('if strings.Contains(name, "..") {'))}},
         R, "BE-1", "the fix changes (moves) the check")
    item("s7", "s7-transform-decode", "qualifier",
         {"subject": both(g, f, 'raw := r.URL.Query().Get("p")'), "transform": both(g, f, decode)},
         R, "QU-1", "without the decode after the check, the check would see the dots",
         kind="transform", semantic={"expected": "must_be_present"})
    item("s7", "s7-transform-decode-polarity", "qualifier",
         {"subject": both(g, f, 'raw := r.URL.Query().Get("p")'), "transform": both(g, f, decode)},
         N, "QU-1", "wrong polarity: the decode must be present", kind="transform",
         semantic={"expected": "must_be_absent"})

    # s8: the fix changes the check nearest the effect (the behavior) and adds an earlier guard
    f = "s8.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    key_def = 'key := r.URL.Query().Get("key")'
    near_v = 'if strings.HasPrefix(key, "/") {'
    near_x = 'if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {'
    added = "if !u.Verified {"
    item("s8", "s8-entry-extracted", "entry", {"entry": both(g, f, key_def)},
         R, "EN-2", "the first extraction of the query parameter")
    item("s8", "s8-behavior-nearest", "behavior",
         {"behavior": {"vuln": present(v(near_v)), "fixed": present(x(near_x))}},
         R, "BE-3", "of the two changed checks, the one nearest the write decides it")
    item("s8", "s8-behavior-earlier-guard", "behavior",
         {"behavior": {"vuln": absent(v(key_def)), "fixed": present(x(added))}},
         N, "BE-3", "the added guard is not the changed check nearest the effect")
    item("s8", "s8-guard-added", "qualifier",
         {"subject": both(g, f, "u Uploader"),
          "predicate": {"vuln": absent(v(key_def)), "fixed": present(x(added))}},
         N, "QU-1", "definitions v2: not necessary, since a verified uploader (account state is not "
         "the attacker's, so any value is admissible) still triggers the effect; v1 labelled it REQUIRED",
         kind="guard", semantic={"expected": "must_not_hold"})
    item("s8", "s8-guard-added-wrong-context", "qualifier",
         {"subject": both(g, f, "u Uploader"),
          "predicate": {"vuln": absent(v(near_v)), "fixed": present(x(added))}},
         N, "AC-1", "the context is the first statement after the if (the key definition)",
         kind="guard", semantic={"expected": "must_not_hold"})
    item("s8", "s8-guard-is-behavior", "qualifier",
         {"subject": both(g, f, key_def),
          "predicate": {"vuln": present(v(near_v)), "fixed": present(x(near_x))}},
         N, "QU-2", "the nearest changed check is the behavior", kind="guard",
         semantic={"expected": "must_not_hold"})

    # s9: the fix extends the nearest check (the behavior) and adds a redundant earlier check that
    # alone would stop every traversal: a required guard absent before the fix (definitions v2)
    f = "s9.go"
    v, x = g(f, "vuln"), g(f, "fixed")
    name_def = 'name := r.URL.Query().Get("name")'
    early = 'if strings.Contains(name, "..") {'
    near_v9 = 'if strings.HasPrefix(name, "/") {'
    near_x9 = 'if strings.HasPrefix(name, "/") || strings.Contains(name, "..") {'
    item("s9", "s9-guard-added-redundant", "qualifier",
         {"subject": both(g, f, name_def),
          "predicate": {"vuln": absent(v(near_v9)), "fixed": present(x(early))}},
         R, "QU-1", "adding the early check to the vulnerable revision would stop every traversal; "
         "the nearest changed check is the behavior (BE-3); context = the statement it protects (AC-1)",
         kind="guard", semantic={"expected": "must_not_hold"})
    item("s9", "s9-guard-added-polarity", "qualifier",
         {"subject": both(g, f, name_def),
          "predicate": {"vuln": absent(v(near_v9)), "fixed": present(x(early))}},
         N, "GU-1", "wrong polarity: the write proceeds only when the written condition is false",
         kind="guard", semantic={"expected": "must_hold"})
    del near_x9

    claims = {
        "s1": ("rdscen-go", "CWE-862 Missing Authorization"),
        "s2": ("rdscen-go", "CWE-22 Path Traversal"),
        "s3": ("rdscen-go", "CWE-89 SQL Injection"),
        "s5": ("rdscen-go", "CWE-200 Exposure of Sensitive Information"),
        "s7": ("rdscen-go", "CWE-22 Path Traversal"),
        "s8": ("rdscen-go", "CWE-22 Path Traversal"),
        "s4": ("rdscen-py", "CWE-347 Improper Verification of Cryptographic Signature"),
        "s6": ("rdscen-py", "CWE-22 Path Traversal"),
        "s9": ("rdscen-go", "CWE-22 Path Traversal"),
    }
    files = {"s1": "s1.go", "s2": "s2.go", "s3": "s3.go", "s5": "s5.go", "s7": "s7.go", "s8": "s8.go",
             "s9": "s9.go",
             "s4": "s4.py", "s6": "s6.py"}
    http = ("The attacker controls the HTTP request (method, URL, query, headers, body). Every other "
            "state (accounts, sessions, policy objects, configuration, environment, files, the root "
            "directory) may take any value the code allows.")
    domains = {sid: http for sid in ("s1", "s2", "s3", "s5", "s7", "s8", "s9")}
    domains["s4"] = ("The attacker controls header, msg and sig. key is the server's secret; ALGS is as "
                     "in the code.")
    domains["s6"] = "The attacker controls user_path. base is any directory path the caller passes."
    scenarios = {sid: {"repo_fixture": repo, "file": files[sid], "domain": domains[sid],
                       "claim": f"In package {'scen' if repo.endswith('go') else files[sid][:-3]}, "
                                f"attacker-controlled input may lead to {cwe}.",
                       "vulnerable_revision": "vuln", "fixed_revision": "fixed"}
                 for sid, (repo, cwe) in claims.items()}
    fixtures = {repo: {"language": "go" if repo.endswith("go") else "python",
                       "repo": f".cache/fixtures/{repo}",
                       "commits": {"vuln": sha(repo, "vuln"), "fixed": sha(repo, "fixed")}}
                for repo in ("rdscen-go", "rdscen-py")}
    return {"set": "rd-boundary-requirements", "fixtures": fixtures, "scenarios": scenarios,
            "items": items}, labels


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def dump(path: Path, header: str, doc: dict) -> None:
    path.write_text(header + yaml.dump(doc, Dumper=_Dumper, sort_keys=False, width=110, allow_unicode=True))


SEED = 20261001

# §15.1: a dispute on a core case removes the relation or kind from the RD vocabulary; on a
# boundary case it makes that boundary INDETERMINATE. Core cases are the plain positive and
# negative instances of each definition; every case testing a numbered edge rule is boundary.
# Fixed before any adjudicator sees a case.
CORE = {
    "oc-direct-argument", "oc-the-earlier-store-itself", "oc-container",
    "ff-through-local", "ff-overwritten",
    "gp-nested-field", "gp-redefined",
    "du-through-local", "du-definition-to-definition", "du-overwritten",
    "ab-static", "ab-first-argument", "ab-receiver",
    "re-local", "re-index",
    "pd-keyword", "pd-parameter-keyword", "pd-overwritten",
    "ct-override",
    "rd-registered", "rd-registered-plain", "rd-unregistered",
    "s2-entry-extracted", "s6-entry-parameter",
    "s3-behavior-sink", "s6-behavior-check",
    "s3-guard-mode", "s7-transform-decode", "s2-config-equals", "s4-dispatch-none",
}


def opaque(rel: dict, rel_labels: dict, req: dict, req_labels: dict) -> None:
    """Descriptive ids give the answer away: adjudicator-facing ids are opaque, in a seeded order
    (requirement items stay grouped by scenario); the descriptive name stays in the labels only."""
    rng = random.Random(SEED)
    hops = list(rel["hops"])
    rng.shuffle(hops)
    new_rel = {}
    for i, h in enumerate(hops, 1):
        new_rel[f"r{i:02d}"] = {"name": h["id"], **rel_labels[h["id"]],
                                "tier": "core" if h["id"] in CORE else "boundary"}
        h["id"] = f"r{i:02d}"
    rel["hops"] = hops
    rel_labels.clear()
    rel_labels.update(new_rel)
    order, new_req = [], {}
    for sid in req["scenarios"]:
        group = [it for it in req["items"] if it["scenario"] == sid]
        rng.shuffle(group)
        order += group
    for i, it in enumerate(order, 1):
        new_req[f"q{i:02d}"] = {"name": it["id"], **req_labels[it["id"]],
                                "tier": "core" if it["id"] in CORE else "boundary"}
        it["id"] = f"q{i:02d}"
    req["items"] = order
    req_labels.clear()
    req_labels.update(new_req)


def main() -> None:
    rel, rel_labels = relation_cases()
    req, req_labels = requirement_cases()
    names = {h["id"] for h in rel["hops"]} | {it["id"] for it in req["items"]}
    assert CORE <= names, sorted(CORE - names)
    opaque(rel, rel_labels, req, req_labels)
    dump(HERE / "relation_cases.yaml",
         "# RD relation boundary cases (adjudicator-facing). Labels: relation_labels.yaml.\n", rel)
    dump(HERE / "relation_labels.yaml",
         "# The author's labels for relation_cases.yaml. Never shown to adjudicators.\n",
         {"set": rel["set"], "labels": rel_labels})
    dump(HERE / "requirement_cases.yaml",
         "# RD requirement-level boundary cases (adjudicator-facing). Labels: requirement_labels.yaml.\n", req)
    dump(HERE / "requirement_labels.yaml",
         "# The author's labels for requirement_cases.yaml. Never shown to adjudicators.\n",
         {"set": req["set"], "labels": req_labels})
    print(f"{len(rel['hops'])} relation cases, {len(req['items'])} requirement items")


if __name__ == "__main__":
    main()
