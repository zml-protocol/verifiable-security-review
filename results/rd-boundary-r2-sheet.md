# Definition check: labeling sheet

Label 19 requirement items (Part 2) against the definitions below. Use only this sheet: the definitions, the code shown and general knowledge of Go and Python. Judge each case on its own.

## How to label

- An anchor written `expr`@N is the program point where the expression `expr` starts on line N of the file shown.
- **Part 2, requirement items**: each scenario states a claim and shows two revisions. With a triggering input, the claimed effect occurs at `vuln` and does not occur at `fixed`. Each item proposes one requirement (an entry, a behavior, or a qualifier with its kind) with its realization at each revision (present with an anchor, or absent with a context). Label `"REQUIRED"` if this exact item, with every field, is a correct requirement under the definitions; `"NOT_REQUIRED"` if it is not (a wrong role, kind, field, state, anchor or context makes it NOT_REQUIRED); `"INDETERMINATE"` if the definitions do not settle it. Items of one scenario may be alternatives to each other; any number of them may be wrong.
- A short note is welcome but optional.

## Definitions (verbatim)

```yaml
version: 2

common:
  - id: C-1
    rule: >
      A hop names two program points ("from" and "to") in one revision. Each point is the place
      where a stated expression starts. A relation either holds between the two points or it
      does not; the definitions below decide which.
  - id: C-2
    rule: >
      "Within the function" means inside the same function or method body. The body of a nested
      function, closure (Go function literal), Python lambda or comprehension is a different
      function, except where a rule says otherwise.
  - id: C-3
    rule: >
      "Local value flow" means a value passes unchanged from one local variable to another by
      assignment (a := x, a = x), including from a parameter. A call does not pass a value by
      local value flow unless a rule says so.

relations:
  object_composition:
    language: go
    definition: >
      `from` is a statement that defines a local variable (v := e, v = e, var v = e) or stores
      into a field through a variable (v.f = e). `to` is a field store x.g = e'. The hop holds
      when the object that `from` defines (or modifies through v) is, by local value flow and
      without passing through any other field store, one of the values `to` stores, or a direct
      part of one.
    rules:
      - id: OC-1
        rule: >
          The values `x.g = e'` stores are e'. For `x.g = append(x.g, a1, ..., an)` they are the
          appended arguments a1 ... an, never x.g itself.
      - id: OC-2
        rule: >
          A direct part of a stored value is a literal element, a keyed value, the operand of
          `&`, or a call argument inside that value's expression, at any depth of that one
          expression.
      - id: OC-3
        rule: >
          Container spread. In `x.g = append(x.g, src...)` the spread container `src` is a stored
          value. The hop from the statement defining the version of `src` that is spread holds:
          one step. How elements got into `src` earlier is a separate, earlier hop; from an
          element's definition to this store does not hold (two steps, not folded into one).
      - id: OC-4
        rule: >
          Version. `from` must define the version of the variable that reaches the stored value
          by local value flow. A definition that is later overwritten does not hold; `v = append(v,
          ...)` defines a new version of v.
      - id: OC-5
        rule: >
          Earlier store. An object that reaches the stored value only by being read back out of
          a field (after an earlier field store put it there) does not hold for `from`'s
          definition. The earlier field store itself is a separate hop.
      - id: OC-6
        rule: The container x of the store `x.g = ...` is not a stored value.
      - id: OC-7
        rule: >
          Pointers and copies. When `from` modifies an object through a pointer variable (p.f =
          e) and the store's value is another variable holding the same pointer, the same object
          is stored: the hop holds. A value copy of a struct (w := v) is a different object;
          modifying the copy does not modify v.

  field_flow:
    language: go
    definition: >
      `from` is a statement defining one or more local variables. `to` is a keyed struct literal
      field `f: e` or a field store `x.f = e`. The hop holds when a value defined at `from`
      reaches e within the function, through local variables and through calls that receive it
      (or a value derived from it) as an argument and derive their result from it.
    rules:
      - id: FF-1
        rule: A statement defining several variables defines each; the hop holds if any of them reaches e.
      - id: FF-2
        rule: A value overwritten before e is evaluated does not reach e.
      - id: FF-3
        rule: >
          Closures. A value that reaches e only through a function literal (a captured variable
          read inside the closure) does not reach e within the function, even when the closure
          is called inside e.
      - id: FF-4
        rule: >
          A call derives its result from an argument when the result can depend on it (e.g. a
          string function). Assignment chains count (C-3).

  guard_property:
    language: go
    definition: >
      `from` is a keyed field `f: e` anywhere inside the composite literal that initializes a
      local variable v at its definition (through nested literals, keyed values and `&`). `to`
      is a field store v.g = e2 whose v reads that same definition of v.
    rules:
      - id: GP-1
        rule: Keyed fields inside nested literals or inside `&T{...}` within the initializer count.
      - id: GP-2
        rule: If v is redefined between the literal and the store, the store reads a different definition; the hop does not hold.
      - id: GP-3
        rule: >
          The relation is structural: it does not judge whether the property matters. Every keyed
          field of the literal, including a sibling field unrelated to the store, holds. Whether a
          property is required is a requirement question (qualifiers, QU-1).

  def_use:
    language: [go, python]
    definition: >
      `from` defines a value: in Go a statement defining local variables, a function parameter,
      or the value variable of a range clause; in Python a parameter or a single-name assignment.
      `to` is a later statement defining a local variable (Python: a single-name assignment)
      whose right-hand side reads that value, or (Go) a call argument whose expression reads it,
      or (Python) a call any of whose positional or keyword arguments reads it. The read must be
      within the function and of the value as defined at `from`, by local value flow.
    rules:
      - id: DU-1
        rule: Reading a variable assigned from the value counts (a := x; b := a + y reads x's value).
      - id: DU-2
        rule: A value overwritten (including a reassigned parameter) before the read does not reach it.
      - id: DU-3
        rule: >
          Reads inside a closure, lambda, nested function or comprehension body do not count
          (C-2). Exception (Python): the outermost iterable of a comprehension is evaluated in the
          enclosing function, so a read there counts.
      - id: DU-4
        rule: A read as the base of a selector or attribute, an index, or a call receiver counts as reading the value.
      - id: DU-5
        rule: A Go statement defining several variables defines each; the hop holds if any of them is read.

  argument_binding:
    language: go
    definition: >
      `from` is argument i of a call (counting from 0, not the receiver). `to` is parameter i of
      a function or method the call can run at run time.
    rules:
      - id: AB-1
        rule: >
          Dynamic calls. A call through an interface value can run the method of a dynamic type T
          only if a value of type T can reach the receiver: through assignments, parameter
          passing, returns and stores in the program. When the receiver comes from a parameter of
          a function that code outside the program can call (an exported function, a registered
          handler), a value of T can also arrive from outside, but only if outside code can obtain
          one (T is exported, or something exported yields a T). Implementing the interface is
          not enough. A call of a function value can run exactly the functions that value can
          hold, by the same reasoning: a function with a matching signature that is never
          assigned to it cannot run. (The verifier follows static resolution only; such true hops
          may stay UNVERIFIED.)
      - id: AB-2
        rule: An argument passed into a variadic parameter's tail is not bound to that parameter (it receives a slice).
      - id: AB-3
        rule: The receiver of a method call is not an argument and is never bound to a parameter.
      - id: AB-4
        rule: Argument i binds parameter i only.

  range_element:
    language: go
    definition: >
      `from` defines a collection (a statement defining a local variable, or a parameter). `to`
      is the value variable of a range clause whose ranged expression is that same value by
      local value flow.
    rules:
      - id: RE-1
        rule: "`for i := range xs` binds the index (or map key), not an element: a one-variable range has no value variable."
      - id: RE-2
        rule: Ranging over a local variable assigned from the collection counts (C-3).
      - id: RE-3
        rule: Ranging over a field or element of the value (range t.Items) is not ranging over the value itself.
      - id: RE-4
        rule: Map values are elements; the value variable of `for k, v := range m` holds.

  call_typed_attribute:
    language: python
    definition: >
      `from` is a call a.b.m(...). The hop holds when, at run time, the call can invoke the
      function whose body contains `to`.
    rules:
      - id: CT-1
        rule: >
          When every object the attribute can hold (by the assignments in the program) is of a
          class whose m overrides the base class's m, the base class's m cannot be invoked.

  registry_dispatch:
    language: python
    definition: >
      `from` is a call r.m(...) where r is looked up from a registry keyed by input data. The hop
      holds when, at run time, the call can invoke the method whose body contains `to`.
    rules:
      - id: RD-1
        rule: A method of a class none of whose instances is ever placed in the registry cannot be invoked through it.

requirements:
  claim: >
    The task states a claim: in a package, attacker-controlled input may lead to a weakness
    (CWE name). A "triggering input" is an attacker-controlled input with which the claimed
    effect occurs at the vulnerable revision. An "admissible execution" is a run of the
    vulnerable revision on a triggering input in which the effect occurs, with every state the
    attacker does not control (accounts, sessions, configuration, environment, files) at any
    value the code allows, unless the scenario states otherwise. The scenario says what the
    attacker controls.
  entry:
    definition: >
      The program point where the attacker-controlled input named in the claim first becomes a
      value in the repository's code.
    rules:
      - id: EN-1
        rule: >
          When a parameter of the exposed function holds exactly that input (for a claim about
          a request as a whole, such as missing authorization or information exposure, the
          request parameter), the entry is that parameter.
      - id: EN-2
        rule: >
          When the input is a part of a larger object (one query parameter of a request, one key
          of a token header), the entry is the first definition that extracts that part, not
          the parameter holding the whole object.
      - id: EN-3
        rule: A value derived from the input after its first extraction is not the entry.
  behavior:
    definition: >
      The program point that decides the security-relevant effect for the triggering input.
    rules:
      - id: BE-1
        rule: >
          When the fix adds, removes or changes a check or a transform on the path, the behavior
          is that check or transform (at each revision where it exists).
      - id: BE-2
        rule: >
          Otherwise (the fix changes the dangerous operation itself, removes it, or changes
          something off the path such as a registry), the behavior is the statement performing
          the security-relevant effect.
      - id: BE-3
        rule: >
          Several changed checks or transforms. When the fix changes more than one check or
          transform on the path, the behavior is the changed one nearest the effect (the last one
          the triggering input passes before the effect) whose result directly decides whether
          the effect occurs. When two candidates cannot be ordered that way (for example, on
          different branches that each decide the effect), the behavior is INDETERMINATE_TRUTH and
          the fixture is replaced under the charter's rule.
  absent_context:
    definition: >
      An element absent at one revision is written as absent with a context: the counterpart, at
      the absent revision, of the statement the element controls or feeds at the present revision.
    rules:
      - id: AC-1
        rule: For a guard, the statement it protects (for `if cond { ...; return }`, the first statement after the if).
      - id: AC-2
        rule: For a transform, the first statement that reads the transformed value.
      - id: AC-3
        rule: >
          For an entry or behavior, the diff-aligned statement: when the element was inserted,
          the statement right after the insertion point; when it was removed, the statement right
          after the removal point (not the one before it).
  state:
    - id: ST-1
      rule: >
        Each anchor is given per revision as present (the code exists there) or absent (it does
        not). A behavior that the fix removes is absent at the fixed revision even though a
        neighboring statement exists there.

qualifiers:
  general:
    - id: QU-1
      rule: >
        Necessity. A guard, transform, config or dispatch target is required only if it is a
        necessary condition of the claimed effect at the vulnerable revision: it holds, in its
        stated sense, in every admissible execution (see claim), and it is not a condition that
        every execution of the code satisfies anyway. Mattering for some inputs or some states
        only is not enough. Per kind:
        guard: every admissible execution passes the predicate with the stated polarity.
        config: every admissible execution needs the stated configuration condition.
        dispatch_target: every admissible execution dispatches the call to the target.
        transform: must_be_present when, with the transform removed (its input passed through
        unchanged), no admissible execution remains; must_be_absent when, with the transform
        applied, none remains.
        An element absent at the vulnerable revision (added by the fix) is required only if
        adding it there, as it is at the fixed revision, would stop the effect in every
        admissible execution; its expected semantics is read at the fixed revision (GU-1).
        A sibling property or a neighboring check without that necessity is not required.
    - id: QU-2
      rule: >
        The one check or transform chosen as the behavior (BE-1, BE-3) is not also a qualifier.
        Other changed checks or transforms can be qualifiers when QU-1 holds.
    - id: QU-3
      rule: >
        Conditions the attacker satisfies by choosing the triggering input (the request method,
        the presence of a parameter) are part of the input, not qualifiers.
    - id: QK-1
      rule: >
        Kind. A condition on a field of an in-memory object is a guard, even when the object was
        built from configuration. `config` is used only when the code reads a configuration
        source by key or name (an environment variable, a configuration map lookup, a flag).
  guard:
    definition: >
      A property of an object on the path that must hold (or must not hold) for the behavior to
      occur. Fields: subject (where the object is defined), predicate (where the property is
      checked), expected.
    rules:
      - id: GU-1
        rule: >
          Polarity. The property is the boolean condition as written at the predicate. expected
          is must_hold when the behavior occurs only if that condition is true, must_not_hold
          when only if it is false (for `if p.M != "raw" { return }`, must_not_hold).
  transform:
    definition: >
      A transformation of a value on the path whose presence or absence decides the behavior.
      Fields: subject (the value transformed), transform (where it is applied), expected:
      must_be_present or must_be_absent for the behavior to occur.
  config:
    definition: >
      A configuration value that must satisfy a condition for the behavior to occur. Fields:
      subject (the statement where the value affects the path), config (the expression that
      reads the configuration item), expected_condition {op: equals | not_equals | set | unset,
      value}.
    rules:
      - id: CF-1
        rule: >
          The condition is the one the behavior needs. `set` means any value; when the code
          compares with a specific value, `set` is not sufficient and the condition is `equals`
          that value.
  dispatch_target:
    definition: >
      The implementation a dynamic call must reach for the behavior to occur. Fields: call (the
      call site), target (the definition of the implementation reached).
```


## Part 2. Requirement scenarios

### Scenario s1 (s1.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-862 Missing Authorization.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import "net/http"
   4 | 
   5 | type Account struct {
   6 | 	Name    string
   7 | 	IsAdmin bool
   8 | }
   9 | 
  10 | type Store struct{ items map[string]string }
  11 | 
  12 | func (s *Store) DeleteAll() { s.items = map[string]string{} }
  13 | 
  14 | var sessions = map[string]Account{}
  15 | 
  16 | func lookup(r *http.Request) Account {
  17 | 	return sessions[r.Header.Get("Cookie")]
  18 | }
  19 | 
  20 | func HandleReset(w http.ResponseWriter, r *http.Request, s *Store) {
  21 | 	u := lookup(r)
  22 | 	w.Header().Set("X-Account", u.Name)
  23 | 	s.DeleteAll()
  24 | 	w.WriteHeader(http.StatusNoContent)
  25 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import "net/http"
   4 | 
   5 | type Account struct {
   6 | 	Name    string
   7 | 	IsAdmin bool
   8 | }
   9 | 
  10 | type Store struct{ items map[string]string }
  11 | 
  12 | func (s *Store) DeleteAll() { s.items = map[string]string{} }
  13 | 
  14 | var sessions = map[string]Account{}
  15 | 
  16 | func lookup(r *http.Request) Account {
  17 | 	return sessions[r.Header.Get("Cookie")]
  18 | }
  19 | 
  20 | func HandleReset(w http.ResponseWriter, r *http.Request, s *Store) {
  21 | 	u := lookup(r)
  22 | 	w.Header().Set("X-Account", u.Name)
  23 | 	if !u.IsAdmin {
  24 | 		w.WriteHeader(http.StatusForbidden)
  25 | 		return
  26 | 	}
  27 | 	s.DeleteAll()
  28 | 	w.WriteHeader(http.StatusNoContent)
  29 | }
```

#### diff

```diff
--- vuln/s1.go
+++ fixed/s1.go
@@ -20,6 +20,10 @@
 func HandleReset(w http.ResponseWriter, r *http.Request, s *Store) {
 	u := lookup(r)
 	w.Header().Set("X-Account", u.Name)
+	if !u.IsAdmin {
+		w.WriteHeader(http.StatusForbidden)
+		return
+	}
 	s.DeleteAll()
 	w.WriteHeader(http.StatusNoContent)
 }
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q06 | qualifier | guard | expected: must_not_hold | subject: vuln present `u := lookup(r)`@21; fixed present `u := lookup(r)`@21<br>predicate: vuln absent (context `s.DeleteAll()`@23); fixed present `if !u.IsAdmin {`@23 |

### Scenario s2 (s2.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | func HandleDownload(w http.ResponseWriter, r *http.Request, root string) {
  11 | 	if os.Getenv("ALLOW_DOWNLOAD") != "1" {
  12 | 		http.Error(w, "disabled", http.StatusForbidden)
  13 | 		return
  14 | 	}
  15 | 	name := r.URL.Query().Get("file")
  16 | 	clean := strings.TrimSpace(name)
  17 | 	data, err := os.ReadFile(filepath.Join(root, clean))
  18 | 	if err != nil {
  19 | 		http.Error(w, "not found", http.StatusNotFound)
  20 | 		return
  21 | 	}
  22 | 	w.Write(data)
  23 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | func HandleDownload(w http.ResponseWriter, r *http.Request, root string) {
  11 | 	if os.Getenv("ALLOW_DOWNLOAD") != "1" {
  12 | 		http.Error(w, "disabled", http.StatusForbidden)
  13 | 		return
  14 | 	}
  15 | 	name := r.URL.Query().Get("file")
  16 | 	clean := strings.TrimSpace(name)
  17 | 	clean = filepath.Base(clean)
  18 | 	data, err := os.ReadFile(filepath.Join(root, clean))
  19 | 	if err != nil {
  20 | 		http.Error(w, "not found", http.StatusNotFound)
  21 | 		return
  22 | 	}
  23 | 	w.Write(data)
  24 | }
```

#### diff

```diff
--- vuln/s2.go
+++ fixed/s2.go
@@ -14,6 +14,7 @@
 	}
 	name := r.URL.Query().Get("file")
 	clean := strings.TrimSpace(name)
+	clean = filepath.Base(clean)
 	data, err := os.ReadFile(filepath.Join(root, clean))
 	if err != nil {
 		http.Error(w, "not found", http.StatusNotFound)
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q07 | qualifier | transform | expected: must_be_absent | subject: vuln present `clean := strings.TrimSpace(name)`@16; fixed present `clean := strings.TrimSpace(name)`@16<br>transform: vuln absent (context `data, err := os.ReadFile(filepath.Join(root, clean))`@17); fixed present `clean = filepath.Base(clean)`@17 |
| q08 | qualifier | config | expected_condition: {op: set} | subject: vuln present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11; fixed present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11<br>config: vuln present `os.Getenv("ALLOW_DOWNLOAD")`@11; fixed present `os.Getenv("ALLOW_DOWNLOAD")`@11 |
| q13 | qualifier | config | expected_condition: {op: equals, value: "1"} | subject: vuln present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11; fixed present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11<br>config: vuln present `os.Getenv("ALLOW_DOWNLOAD")`@11; fixed present `os.Getenv("ALLOW_DOWNLOAD")`@11 |
| q15 | qualifier | transform | expected: must_be_present | subject: vuln present `name := r.URL.Query().Get("file")`@15; fixed present `name := r.URL.Query().Get("file")`@15<br>transform: vuln present `clean := strings.TrimSpace(name)`@16; fixed present `clean := strings.TrimSpace(name)`@16 |

### Scenario s3 (s3.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-89 SQL Injection.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"database/sql"
   5 | 	"net/http"
   6 | )
   7 | 
   8 | type Policy struct {
   9 | 	Mode  string
  10 | 	Label string
  11 | }
  12 | 
  13 | func HandleSearch(w http.ResponseWriter, r *http.Request, db *sql.DB, p Policy) {
  14 | 	if r.Method != http.MethodPost {
  15 | 		http.Error(w, "method", http.StatusMethodNotAllowed)
  16 | 		return
  17 | 	}
  18 | 	if p.Mode != "raw" {
  19 | 		http.Error(w, "unsupported", http.StatusBadRequest)
  20 | 		return
  21 | 	}
  22 | 	if p.Label != "" {
  23 | 		w.Header().Set("X-Policy", p.Label)
  24 | 	}
  25 | 	term := r.FormValue("q")
  26 | 	rows, err := db.Query("SELECT name FROM items WHERE name = '" + term + "'")
  27 | 	if err != nil {
  28 | 		http.Error(w, "error", http.StatusInternalServerError)
  29 | 		return
  30 | 	}
  31 | 	defer rows.Close()
  32 | 	w.WriteHeader(http.StatusOK)
  33 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"database/sql"
   5 | 	"net/http"
   6 | )
   7 | 
   8 | type Policy struct {
   9 | 	Mode  string
  10 | 	Label string
  11 | }
  12 | 
  13 | func HandleSearch(w http.ResponseWriter, r *http.Request, db *sql.DB, p Policy) {
  14 | 	if r.Method != http.MethodPost {
  15 | 		http.Error(w, "method", http.StatusMethodNotAllowed)
  16 | 		return
  17 | 	}
  18 | 	if p.Mode != "raw" {
  19 | 		http.Error(w, "unsupported", http.StatusBadRequest)
  20 | 		return
  21 | 	}
  22 | 	if p.Label != "" {
  23 | 		w.Header().Set("X-Policy", p.Label)
  24 | 	}
  25 | 	term := r.FormValue("q")
  26 | 	rows, err := db.Query("SELECT name FROM items WHERE name = ?", term)
  27 | 	if err != nil {
  28 | 		http.Error(w, "error", http.StatusInternalServerError)
  29 | 		return
  30 | 	}
  31 | 	defer rows.Close()
  32 | 	w.WriteHeader(http.StatusOK)
  33 | }
```

#### diff

```diff
--- vuln/s3.go
+++ fixed/s3.go
@@ -23,7 +23,7 @@
 		w.Header().Set("X-Policy", p.Label)
 	}
 	term := r.FormValue("q")
-	rows, err := db.Query("SELECT name FROM items WHERE name = '" + term + "'")
+	rows, err := db.Query("SELECT name FROM items WHERE name = ?", term)
 	if err != nil {
 		http.Error(w, "error", http.StatusInternalServerError)
 		return
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q16 | qualifier | guard | expected: must_hold | subject: vuln present `p Policy`@13; fixed present `p Policy`@13<br>predicate: vuln present `if p.Label != "" {`@22; fixed present `if p.Label != "" {`@22 |
| q18 | qualifier | guard | expected: must_not_hold | subject: vuln present `r *http.Request`@13; fixed present `r *http.Request`@13<br>predicate: vuln present `if r.Method != http.MethodPost {`@14; fixed present `if r.Method != http.MethodPost {`@14 |
| q19 | qualifier | guard | expected: must_not_hold | subject: vuln present `p Policy`@13; fixed present `p Policy`@13<br>predicate: vuln present `if p.Mode != "raw" {`@18; fixed present `if p.Mode != "raw" {`@18 |
| q20 | qualifier | guard | expected: must_hold | subject: vuln present `p Policy`@13; fixed present `p Policy`@13<br>predicate: vuln present `if p.Mode != "raw" {`@18; fixed present `if p.Mode != "raw" {`@18 |

### Scenario s7 (s7.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"net/url"
   6 | 	"os"
   7 | 	"path/filepath"
   8 | 	"strings"
   9 | )
  10 | 
  11 | func HandleFile(w http.ResponseWriter, r *http.Request, root string) {
  12 | 	raw := r.URL.Query().Get("p")
  13 | 	if strings.Contains(raw, "..") {
  14 | 		http.Error(w, "bad path", http.StatusBadRequest)
  15 | 		return
  16 | 	}
  17 | 	name, err := url.QueryUnescape(raw)
  18 | 	if err != nil {
  19 | 		http.Error(w, "bad escape", http.StatusBadRequest)
  20 | 		return
  21 | 	}
  22 | 	data, err := os.ReadFile(filepath.Join(root, name))
  23 | 	if err != nil {
  24 | 		http.Error(w, "not found", http.StatusNotFound)
  25 | 		return
  26 | 	}
  27 | 	w.Write(data)
  28 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"net/url"
   6 | 	"os"
   7 | 	"path/filepath"
   8 | 	"strings"
   9 | )
  10 | 
  11 | func HandleFile(w http.ResponseWriter, r *http.Request, root string) {
  12 | 	raw := r.URL.Query().Get("p")
  13 | 	name, err := url.QueryUnescape(raw)
  14 | 	if err != nil {
  15 | 		http.Error(w, "bad escape", http.StatusBadRequest)
  16 | 		return
  17 | 	}
  18 | 	if strings.Contains(name, "..") {
  19 | 		http.Error(w, "bad path", http.StatusBadRequest)
  20 | 		return
  21 | 	}
  22 | 	data, err := os.ReadFile(filepath.Join(root, name))
  23 | 	if err != nil {
  24 | 		http.Error(w, "not found", http.StatusNotFound)
  25 | 		return
  26 | 	}
  27 | 	w.Write(data)
  28 | }
```

#### diff

```diff
--- vuln/s7.go
+++ fixed/s7.go
@@ -10,13 +10,13 @@
 
 func HandleFile(w http.ResponseWriter, r *http.Request, root string) {
 	raw := r.URL.Query().Get("p")
-	if strings.Contains(raw, "..") {
-		http.Error(w, "bad path", http.StatusBadRequest)
-		return
-	}
 	name, err := url.QueryUnescape(raw)
 	if err != nil {
 		http.Error(w, "bad escape", http.StatusBadRequest)
+		return
+	}
+	if strings.Contains(name, "..") {
+		http.Error(w, "bad path", http.StatusBadRequest)
 		return
 	}
 	data, err := os.ReadFile(filepath.Join(root, name))
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q26 | qualifier | transform | expected: must_be_absent | subject: vuln present `raw := r.URL.Query().Get("p")`@12; fixed present `raw := r.URL.Query().Get("p")`@12<br>transform: vuln present `name, err := url.QueryUnescape(raw)`@17; fixed present `name, err := url.QueryUnescape(raw)`@13 |
| q27 | qualifier | transform | expected: must_be_present | subject: vuln present `raw := r.URL.Query().Get("p")`@12; fixed present `raw := r.URL.Query().Get("p")`@12<br>transform: vuln present `name, err := url.QueryUnescape(raw)`@17; fixed present `name, err := url.QueryUnescape(raw)`@13 |

### Scenario s8 (s8.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | type Uploader struct {
  11 | 	Name     string
  12 | 	Verified bool
  13 | }
  14 | 
  15 | func HandleUpload(w http.ResponseWriter, r *http.Request, u Uploader, root string, data []byte) {
  16 | 	key := r.URL.Query().Get("key")
  17 | 	if strings.HasPrefix(key, "/") {
  18 | 		http.Error(w, "bad key", http.StatusBadRequest)
  19 | 		return
  20 | 	}
  21 | 	err := os.WriteFile(filepath.Join(root, key), data, 0o600)
  22 | 	if err != nil {
  23 | 		http.Error(w, "write failed", http.StatusInternalServerError)
  24 | 		return
  25 | 	}
  26 | 	w.WriteHeader(http.StatusCreated)
  27 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | type Uploader struct {
  11 | 	Name     string
  12 | 	Verified bool
  13 | }
  14 | 
  15 | func HandleUpload(w http.ResponseWriter, r *http.Request, u Uploader, root string, data []byte) {
  16 | 	if !u.Verified {
  17 | 		http.Error(w, "unverified", http.StatusForbidden)
  18 | 		return
  19 | 	}
  20 | 	key := r.URL.Query().Get("key")
  21 | 	if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {
  22 | 		http.Error(w, "bad key", http.StatusBadRequest)
  23 | 		return
  24 | 	}
  25 | 	err := os.WriteFile(filepath.Join(root, key), data, 0o600)
  26 | 	if err != nil {
  27 | 		http.Error(w, "write failed", http.StatusInternalServerError)
  28 | 		return
  29 | 	}
  30 | 	w.WriteHeader(http.StatusCreated)
  31 | }
```

#### diff

```diff
--- vuln/s8.go
+++ fixed/s8.go
@@ -13,8 +13,12 @@
 }
 
 func HandleUpload(w http.ResponseWriter, r *http.Request, u Uploader, root string, data []byte) {
+	if !u.Verified {
+		http.Error(w, "unverified", http.StatusForbidden)
+		return
+	}
 	key := r.URL.Query().Get("key")
-	if strings.HasPrefix(key, "/") {
+	if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {
 		http.Error(w, "bad key", http.StatusBadRequest)
 		return
 	}
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q30 | qualifier | guard | expected: must_not_hold | subject: vuln present `key := r.URL.Query().Get("key")`@16; fixed present `key := r.URL.Query().Get("key")`@20<br>predicate: vuln present `if strings.HasPrefix(key, "/") {`@17; fixed present `if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {`@21 |
| q32 | qualifier | guard | expected: must_not_hold | subject: vuln present `u Uploader`@15; fixed present `u Uploader`@15<br>predicate: vuln absent (context `key := r.URL.Query().Get("key")`@16); fixed present `if !u.Verified {`@16 |
| q35 | qualifier | guard | expected: must_not_hold | subject: vuln present `u Uploader`@15; fixed present `u Uploader`@15<br>predicate: vuln absent (context `if strings.HasPrefix(key, "/") {`@17); fixed present `if !u.Verified {`@16 |

### Scenario s4 (s4.py)

**Claim:** In package s4, attacker-controlled input may lead to CWE-347 Improper Verification of Cryptographic Signature.

**What the attacker controls; other state:** The attacker controls header, msg and sig. key is the server's secret; ALGS is as in the code.

#### vuln

```python
   1 | """RD boundary scenario (synthetic)."""
   2 | import hashlib
   3 | import hmac
   4 | 
   5 | 
   6 | class NoneAlg:
   7 |     def verify(self, msg, sig, key):
   8 |         return sig == b""
   9 | 
  10 | 
  11 | class HmacAlg:
  12 |     def verify(self, msg, sig, key):
  13 |         return hmac.compare_digest(sig, hmac.new(key, msg, hashlib.sha256).digest())
  14 | 
  15 | 
  16 | ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}
  17 | 
  18 | 
  19 | def check(header, msg, sig, key):
  20 |     name = header["alg"]
  21 |     alg = ALGS[name]
  22 |     return alg.verify(msg, sig, key)
```

#### fixed

```python
   1 | """RD boundary scenario (synthetic)."""
   2 | import hashlib
   3 | import hmac
   4 | 
   5 | 
   6 | class NoneAlg:
   7 |     def verify(self, msg, sig, key):
   8 |         return sig == b""
   9 | 
  10 | 
  11 | class HmacAlg:
  12 |     def verify(self, msg, sig, key):
  13 |         return hmac.compare_digest(sig, hmac.new(key, msg, hashlib.sha256).digest())
  14 | 
  15 | 
  16 | ALGS = {"HS256": HmacAlg()}
  17 | 
  18 | 
  19 | def check(header, msg, sig, key):
  20 |     name = header["alg"]
  21 |     alg = ALGS[name]
  22 |     return alg.verify(msg, sig, key)
```

#### diff

```diff
--- vuln/s4.py
+++ fixed/s4.py
@@ -13,7 +13,7 @@
         return hmac.compare_digest(sig, hmac.new(key, msg, hashlib.sha256).digest())
 
 
-ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}
+ALGS = {"HS256": HmacAlg()}
 
 
 def check(header, msg, sig, key):
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q36 | qualifier | dispatch_target |  | call: vuln present `alg.verify(msg, sig, key)`@22; fixed present `alg.verify(msg, sig, key)`@22<br>target: vuln present `def verify(self, msg, sig, key):`@7; fixed present `def verify(self, msg, sig, key):`@7 |
| q40 | qualifier | dispatch_target |  | call: vuln present `alg.verify(msg, sig, key)`@22; fixed present `alg.verify(msg, sig, key)`@22<br>target: vuln present `def verify(self, msg, sig, key):`@12; fixed present `def verify(self, msg, sig, key):`@12 |

### Scenario s6 (s6.py)

**Claim:** In package s6, attacker-controlled input may lead to CWE-22 Path Traversal.

**What the attacker controls; other state:** The attacker controls user_path. base is any directory path the caller passes.

#### vuln

```python
   1 | """RD boundary scenario (synthetic)."""
   2 | import os
   3 | 
   4 | 
   5 | def safe_path(base, user_path):
   6 |     full = os.path.normpath(os.path.join(base, user_path))
   7 |     if not full.startswith(base):
   8 |         raise ValueError("outside")
   9 |     return full
```

#### fixed

```python
   1 | """RD boundary scenario (synthetic)."""
   2 | import os
   3 | 
   4 | 
   5 | def safe_path(base, user_path):
   6 |     full = os.path.normpath(os.path.join(base, user_path))
   7 |     if os.path.commonpath([full, base]) != base:
   8 |         raise ValueError("outside")
   9 |     return full
```

#### diff

```diff
--- vuln/s6.py
+++ fixed/s6.py
@@ -4,6 +4,6 @@
 
 def safe_path(base, user_path):
     full = os.path.normpath(os.path.join(base, user_path))
-    if not full.startswith(base):
+    if os.path.commonpath([full, base]) != base:
         raise ValueError("outside")
     return full
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q45 | qualifier | transform | expected: must_be_present | subject: vuln present `user_path`@5; fixed present `user_path`@5<br>transform: vuln present `full = os.path.normpath(os.path.join(base, user_path))`@6; fixed present `full = os.path.normpath(os.path.join(base, user_path))`@6 |

### Scenario s9 (s9.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

**What the attacker controls; other state:** The attacker controls the HTTP request (method, URL, query, headers, body). Every other state (accounts, sessions, policy objects, configuration, environment, files, the root directory) may take any value the code allows.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | func HandleExport(w http.ResponseWriter, r *http.Request, root string, data []byte) {
  11 | 	name := r.URL.Query().Get("name")
  12 | 	if strings.HasPrefix(name, "/") {
  13 | 		http.Error(w, "bad name", http.StatusBadRequest)
  14 | 		return
  15 | 	}
  16 | 	err := os.WriteFile(filepath.Join(root, name), data, 0o600)
  17 | 	if err != nil {
  18 | 		http.Error(w, "write failed", http.StatusInternalServerError)
  19 | 		return
  20 | 	}
  21 | 	w.WriteHeader(http.StatusCreated)
  22 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"net/http"
   5 | 	"os"
   6 | 	"path/filepath"
   7 | 	"strings"
   8 | )
   9 | 
  10 | func HandleExport(w http.ResponseWriter, r *http.Request, root string, data []byte) {
  11 | 	name := r.URL.Query().Get("name")
  12 | 	if strings.Contains(name, "..") {
  13 | 		http.Error(w, "dot segments", http.StatusBadRequest)
  14 | 		return
  15 | 	}
  16 | 	if strings.HasPrefix(name, "/") || strings.Contains(name, "..") {
  17 | 		http.Error(w, "bad name", http.StatusBadRequest)
  18 | 		return
  19 | 	}
  20 | 	err := os.WriteFile(filepath.Join(root, name), data, 0o600)
  21 | 	if err != nil {
  22 | 		http.Error(w, "write failed", http.StatusInternalServerError)
  23 | 		return
  24 | 	}
  25 | 	w.WriteHeader(http.StatusCreated)
  26 | }
```

#### diff

```diff
--- vuln/s9.go
+++ fixed/s9.go
@@ -9,7 +9,11 @@
 
 func HandleExport(w http.ResponseWriter, r *http.Request, root string, data []byte) {
 	name := r.URL.Query().Get("name")
-	if strings.HasPrefix(name, "/") {
+	if strings.Contains(name, "..") {
+		http.Error(w, "dot segments", http.StatusBadRequest)
+		return
+	}
+	if strings.HasPrefix(name, "/") || strings.Contains(name, "..") {
 		http.Error(w, "bad name", http.StatusBadRequest)
 		return
 	}
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q47 | qualifier | guard | expected: must_not_hold | subject: vuln present `name := r.URL.Query().Get("name")`@11; fixed present `name := r.URL.Query().Get("name")`@11<br>predicate: vuln absent (context `if strings.HasPrefix(name, "/") {`@12); fixed present `if strings.Contains(name, "..") {`@12 |
| q48 | qualifier | guard | expected: must_hold | subject: vuln present `name := r.URL.Query().Get("name")`@11; fixed present `name := r.URL.Query().Get("name")`@11<br>predicate: vuln absent (context `if strings.HasPrefix(name, "/") {`@12); fixed present `if strings.Contains(name, "..") {`@12 |

## Output

Reply with YAML in exactly the form of the template (`rd-boundary-labels.template.yaml`): `relations` left empty, every id in Part 2 under `requirements`. Write every label and the date as a quoted string.
