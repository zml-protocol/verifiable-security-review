# Definition check: labeling sheet

Label 48 relation cases (Part 1) and 46 requirement items (Part 2) against the definitions below. Use only this sheet: the definitions, the code shown and general knowledge of Go and Python. Judge each case on its own.

## How to label

- An anchor written `expr`@N is the program point where the expression `expr` starts on line N of the file shown.
- **Part 1, relation cases**: `"TRUE"` if the named relation holds from `from` to `to` under the definitions; `"FALSE"` if it does not; `"INDETERMINATE"` if the definitions do not settle it.
- **Part 2, requirement items**: each scenario states a claim and shows two revisions. With a triggering input, the claimed effect occurs at `vuln` and does not occur at `fixed`. Each item proposes one requirement (an entry, a behavior, or a qualifier with its kind) with its realization at each revision (present with an anchor, or absent with a context). Label `"REQUIRED"` if this exact item, with every field, is a correct requirement under the definitions; `"NOT_REQUIRED"` if it is not (a wrong role, kind, field, state, anchor or context makes it NOT_REQUIRED); `"INDETERMINATE"` if the definitions do not settle it. Items of one scenario may be alternatives to each other; any number of them may be wrong.
- A short note is welcome but optional.

## Definitions (verbatim)

```yaml
version: 1

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
    (CWE name). The "triggering input" is an input with which the claimed effect occurs at the
    vulnerable revision.
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
        Relevance. A guard, transform, config or dispatch target is required only if, all else
        fixed, changing it changes whether the security-relevant effect occurs for the triggering
        input at the vulnerable revision. Changing includes adding it where it is absent and
        removing it where it is present: a guard the fix adds is relevant when adding it to the
        vulnerable revision would block the effect. A sibling property or a neighboring check
        without that dependence is not required.
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

## Part 1. Relation cases

### bound.go (go)

```go
   1 | package rdbound
   2 | 
   3 | import "strings"
   4 | 
   5 | type Route struct {
   6 | 	Handler string
   7 | 	Tags    []string
   8 | }
   9 | 
  10 | type Meta struct {
  11 | 	Owner string
  12 | 	Level int
  13 | }
  14 | 
  15 | type Table struct {
  16 | 	Name   string
  17 | 	Routes []Route
  18 | 	Meta   *Meta
  19 | }
  20 | 
  21 | type Sink interface {
  22 | 	Put(k string)
  23 | }
  24 | 
  25 | type memSink struct{ keys []string }
  26 | 
  27 | func (m *memSink) Put(k string) { m.keys = append(m.keys, k) }
  28 | 
  29 | func clean(s string) string { return strings.TrimSpace(s) }
  30 | 
  31 | func join(prefix string, parts ...string) string { return prefix + strings.Join(parts, ",") }
  32 | 
  33 | func split(s string) (string, error) { return s, nil }
  34 | 
  35 | // ---- object_composition
  36 | 
  37 | func Spread(t *Table, h string) {
  38 | 	batch := []Route{}
  39 | 	r := Route{Handler: h}
  40 | 	batch = append(batch, r)
  41 | 	t.Routes = append(t.Routes, batch...)
  42 | }
  43 | 
  44 | func Direct(t *Table, h string) {
  45 | 	one := Route{Handler: h}
  46 | 	t.Routes = append(t.Routes, one)
  47 | }
  48 | 
  49 | func Earlier(t *Table) {
  50 | 	m := &Meta{Level: 1}
  51 | 	holder := &Table{}
  52 | 	holder.Meta = m
  53 | 	t.Meta = holder.Meta
  54 | }
  55 | 
  56 | func Self() Table {
  57 | 	x := Table{Name: "a"}
  58 | 	item := Route{Handler: "h"}
  59 | 	x.Routes = append(x.Routes, item)
  60 | 	return x
  61 | }
  62 | 
  63 | func Alias(t *Table, owner string) {
  64 | 	pm := &Meta{}
  65 | 	p := pm
  66 | 	p.Owner = owner
  67 | 	t.Meta = pm
  68 | }
  69 | 
  70 | func Copy(t *Table, owner string) {
  71 | 	v := Meta{}
  72 | 	w := v
  73 | 	w.Owner = owner
  74 | 	t.Meta = &v
  75 | }
  76 | 
  77 | // ---- field_flow
  78 | 
  79 | func Flow(raw string, other string) Route {
  80 | 	name := clean(raw)
  81 | 	name2 := name
  82 | 	tag := other
  83 | 	tag = "fixed"
  84 | 	label := func() string { return name }
  85 | 	return Route{Handler: name2, Tags: []string{tag, label()}}
  86 | }
  87 | 
  88 | func Multi(s string) Route {
  89 | 	head, rest, _ := strings.Cut(s, ":")
  90 | 	return Route{Handler: rest, Tags: []string{head}}
  91 | }
  92 | 
  93 | // ---- guard_property
  94 | 
  95 | func Guarded(t *Table, h string) {
  96 | 	cfg := Table{
  97 | 		Name: "guard",
  98 | 		Meta: &Meta{Level: 2},
  99 | 	}
 100 | 	cfg.Routes = append(cfg.Routes, Route{Handler: h})
 101 | 	t.Meta = cfg.Meta
 102 | 	cfg = Table{Name: "reset"}
 103 | 	cfg.Name = h
 104 | 	t.Name = cfg.Name
 105 | }
 106 | 
 107 | // ---- def_use
 108 | 
 109 | func Uses(in string, sink Sink) string {
 110 | 	a := in
 111 | 	b := a + "/x"
 112 | 	a = "reset"
 113 | 	c := strings.ToUpper(a)
 114 | 	f := func() { sink.Put(b) }
 115 | 	f()
 116 | 	t := Table{Name: b}
 117 | 	d := t.Name
 118 | 	k, err := split(b)
 119 | 	if err != nil {
 120 | 		return ""
 121 | 	}
 122 | 	sink.Put(k)
 123 | 	return c + d
 124 | }
 125 | 
 126 | // ---- argument_binding
 127 | 
 128 | type nopSink struct{}
 129 | 
 130 | func (nopSink) Put(k string) {}
 131 | 
 132 | func Bind(sink Sink, ms *memSink, x string) string {
 133 | 	sink.Put(x)
 134 | 	ms.Put(x)
 135 | 	out := join("p", x, "q")
 136 | 	return out + join(x)
 137 | }
 138 | 
 139 | func Use() string {
 140 | 	return Bind(&memSink{}, &memSink{}, "z")
 141 | }
 142 | 
 143 | func shout(s string) string { return strings.ToUpper(s) + "!" }
 144 | 
 145 | func Apply(x string) string {
 146 | 	apply := clean
 147 | 	return apply(x)
 148 | }
 149 | 
 150 | // ---- range_element
 151 | 
 152 | func Ranges(names []string, t Table, m map[string]int) int {
 153 | 	list := names
 154 | 	n := 0
 155 | 	for i := range list {
 156 | 		n += i
 157 | 	}
 158 | 	for _, v := range list {
 159 | 		n += len(v)
 160 | 	}
 161 | 	for _, r := range t.Routes {
 162 | 		n += len(r.Handler)
 163 | 	}
 164 | 	for k, c := range m {
 165 | 		n += len(k) + c
 166 | 	}
 167 | 	return n
 168 | }
```

### bound.py (python)

```python
   1 | """RD boundary module (synthetic; not an evaluation fixture)."""
   2 | 
   3 | 
   4 | class Store:
   5 |     def save(self, name, payload):
   6 |         return name
   7 | 
   8 | 
   9 | class AuditStore(Store):
  10 |     def save(self, name, payload):
  11 |         return payload
  12 | 
  13 | 
  14 | class Service:
  15 |     def __init__(self):
  16 |         self.store = AuditStore()
  17 | 
  18 |     def run(self, name, payload):
  19 |         return self.store.save(name, payload)
  20 | 
  21 | 
  22 | class Plain:
  23 |     def render(self, text):
  24 |         return text
  25 | 
  26 | 
  27 | class Upper:
  28 |     def render(self, text):
  29 |         return text.upper()
  30 | 
  31 | 
  32 | class Hidden:
  33 |     def render(self, text):
  34 |         return ""
  35 | 
  36 | 
  37 | RENDERERS = {"plain": Plain(), "upper": Upper()}
  38 | 
  39 | 
  40 | def render(kind, text):
  41 |     r = RENDERERS[kind]
  42 |     return r.render(text)
  43 | 
  44 | 
  45 | def handle(request, user, store):
  46 |     body = request.read()
  47 |     body = body.strip()
  48 |     items = [x for x in [body]]
  49 |     later = [body for _ in range(1)]
  50 |     fn = lambda: body  # noqa: E731
  51 |     saved = store.save(name=user, payload=body)
  52 |     user = None
  53 |     return [store.save(user, fn()), items, later, saved]
```

| id | file | relation | from | to |
|---|---|---|---|---|
| r01 | bound.go | def_use | `in string`@109 | `b := a + "/x"`@111 |
| r02 | bound.go | object_composition | `batch := []Route{}`@38 | `t.Routes = append(t.Routes, batch...)`@41 |
| r03 | bound.go | guard_property | `Level: 2`@98 | `cfg.Routes = append(cfg.Routes, Route{Handler: h})`@100 |
| r04 | bound.py | def_use | `body = request.read()`@46 | `saved = store.save(name=user, payload=body)`@51 |
| r05 | bound.go | object_composition | `one := Route{Handler: h}`@45 | `t.Routes = append(t.Routes, one)`@46 |
| r06 | bound.py | call_typed_attribute | `self.store.save(name, payload)`@19 | `return name`@6 |
| r07 | bound.go | argument_binding | `x)`@133 | `k string`@27 |
| r08 | bound.py | def_use | `body = body.strip()`@47 | `later = [body for _ in range(1)]`@49 |
| r09 | bound.go | range_element | `list := names`@153 | `v := range list`@158 |
| r10 | bound.go | argument_binding | `x, "q")`@135 | `parts ...string`@31 |
| r11 | bound.go | def_use | `b := a + "/x"`@111 | `k, err := split(b)`@118 |
| r12 | bound.go | def_use | `t := Table{Name: b}`@116 | `d := t.Name`@117 |
| r13 | bound.py | registry_dispatch | `r.render(text)`@42 | `return text.upper()`@29 |
| r14 | bound.go | object_composition | `m := &Meta{Level: 1}`@50 | `holder.Meta = m`@52 |
| r15 | bound.go | range_element | `m map[string]int`@152 | `c := range m`@164 |
| r16 | bound.go | guard_property | `Level: 2`@98 | `cfg.Name = h`@103 |
| r17 | bound.py | registry_dispatch | `r.render(text)`@42 | `return ""`@34 |
| r18 | bound.py | def_use | `body = body.strip()`@47 | `store.save(user, fn())`@53 |
| r19 | bound.py | registry_dispatch | `r.render(text)`@42 | `return text`@24 |
| r20 | bound.go | def_use | `a := in`@110 | `c := strings.ToUpper(a)`@113 |
| r21 | bound.py | def_use | `user, store`@45 | `saved = store.save(name=user, payload=body)`@51 |
| r22 | bound.go | object_composition | `batch = append(batch, r)`@40 | `t.Routes = append(t.Routes, batch...)`@41 |
| r23 | bound.go | range_element | `list := names`@153 | `i := range list`@155 |
| r24 | bound.go | argument_binding | `x)`@136 | `prefix string`@31 |
| r25 | bound.py | call_typed_attribute | `self.store.save(name, payload)`@19 | `return payload`@11 |
| r26 | bound.go | argument_binding | `x)`@134 | `k string`@27 |
| r27 | bound.py | def_use | `request, user, store`@45 | `body = request.read()`@46 |
| r28 | bound.go | def_use | `b := a + "/x"`@111 | `b) }`@114 |
| r29 | bound.go | range_element | `names []string`@152 | `v := range list`@158 |
| r30 | bound.go | field_flow | `tag := other`@82 | `Tags: []string{tag, label()}`@85 |
| r31 | bound.go | object_composition | `x := Table{Name: "a"}`@57 | `x.Routes = append(x.Routes, item)`@59 |
| r32 | bound.go | argument_binding | `x)`@147 | `s string`@29 |
| r33 | bound.go | argument_binding | `ms.Put(x)`@134 | `m *memSink`@27 |
| r34 | bound.go | field_flow | `name := clean(raw)`@80 | `Tags: []string{tag, label()}`@85 |
| r35 | bound.go | object_composition | `r := Route{Handler: h}`@39 | `t.Routes = append(t.Routes, batch...)`@41 |
| r36 | bound.go | object_composition | `w.Owner = owner`@73 | `t.Meta = &v`@74 |
| r37 | bound.go | object_composition | `m := &Meta{Level: 1}`@50 | `t.Meta = holder.Meta`@53 |
| r38 | bound.go | field_flow | `head, rest, _ := strings.Cut(s, ":")`@89 | `Handler: rest`@90 |
| r39 | bound.go | field_flow | `name := clean(raw)`@80 | `Handler: name2`@85 |
| r40 | bound.py | def_use | `body = body.strip()`@47 | `items = [x for x in [body]]`@48 |
| r41 | bound.go | object_composition | `p.Owner = owner`@66 | `t.Meta = pm`@67 |
| r42 | bound.go | argument_binding | `x)`@147 | `s string`@143 |
| r43 | bound.py | def_use | `user, store`@45 | `store.save(user, fn())`@53 |
| r44 | bound.py | def_use | `body = body.strip()`@47 | `store.save(name=user, payload=body)`@51 |
| r45 | bound.go | range_element | `t Table`@152 | `r := range t.Routes`@161 |
| r46 | bound.go | argument_binding | `x)`@133 | `k string`@130 |
| r47 | bound.go | def_use | `k, err := split(b)`@118 | `k)`@122 |
| r48 | bound.go | guard_property | `Name: "guard"`@97 | `cfg.Routes = append(cfg.Routes, Route{Handler: h})`@100 |

## Part 2. Requirement scenarios

### Scenario s1 (s1.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-862 Missing Authorization.

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
| q01 | behavior |  |  | behavior: vuln absent (context `w.Header().Set("X-Account", u.Name)`@22); fixed present `if !u.IsAdmin {`@23 |
| q02 | behavior |  |  | behavior: vuln present `s.DeleteAll()`@23; fixed present `s.DeleteAll()`@27 |
| q03 | entry |  |  | entry: vuln present `r *http.Request`@20; fixed present `r *http.Request`@20 |
| q04 | behavior |  |  | behavior: vuln absent (context `s.DeleteAll()`@23); fixed present `if !u.IsAdmin {`@23 |
| q05 | entry |  |  | entry: vuln present `u := lookup(r)`@21; fixed present `u := lookup(r)`@21 |
| q06 | qualifier | guard | expected: must_not_hold | subject: vuln present `u := lookup(r)`@21; fixed present `u := lookup(r)`@21<br>predicate: vuln absent (context `s.DeleteAll()`@23); fixed present `if !u.IsAdmin {`@23 |

### Scenario s2 (s2.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

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
| q09 | entry |  |  | entry: vuln present `clean := strings.TrimSpace(name)`@16; fixed present `clean := strings.TrimSpace(name)`@16 |
| q10 | behavior |  |  | behavior: vuln absent (context `data, err := os.ReadFile(filepath.Join(root, clean))`@17); fixed present `clean = filepath.Base(clean)`@17 |
| q11 | entry |  |  | entry: vuln present `r *http.Request`@10; fixed present `r *http.Request`@10 |
| q12 | behavior |  |  | behavior: vuln present `data, err := os.ReadFile(filepath.Join(root, clean))`@17; fixed present `data, err := os.ReadFile(filepath.Join(root, clean))`@18 |
| q13 | qualifier | config | expected_condition: {op: equals, value: "1"} | subject: vuln present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11; fixed present `if os.Getenv("ALLOW_DOWNLOAD") != "1" {`@11<br>config: vuln present `os.Getenv("ALLOW_DOWNLOAD")`@11; fixed present `os.Getenv("ALLOW_DOWNLOAD")`@11 |
| q14 | entry |  |  | entry: vuln present `name := r.URL.Query().Get("file")`@15; fixed present `name := r.URL.Query().Get("file")`@15 |
| q15 | qualifier | transform | expected: must_be_present | subject: vuln present `name := r.URL.Query().Get("file")`@15; fixed present `name := r.URL.Query().Get("file")`@15<br>transform: vuln present `clean := strings.TrimSpace(name)`@16; fixed present `clean := strings.TrimSpace(name)`@16 |

### Scenario s3 (s3.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-89 SQL Injection.

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
| q17 | entry |  |  | entry: vuln present `term := r.FormValue("q")`@25; fixed present `term := r.FormValue("q")`@25 |
| q18 | qualifier | guard | expected: must_not_hold | subject: vuln present `r *http.Request`@13; fixed present `r *http.Request`@13<br>predicate: vuln present `if r.Method != http.MethodPost {`@14; fixed present `if r.Method != http.MethodPost {`@14 |
| q19 | qualifier | guard | expected: must_not_hold | subject: vuln present `p Policy`@13; fixed present `p Policy`@13<br>predicate: vuln present `if p.Mode != "raw" {`@18; fixed present `if p.Mode != "raw" {`@18 |
| q20 | qualifier | guard | expected: must_hold | subject: vuln present `p Policy`@13; fixed present `p Policy`@13<br>predicate: vuln present `if p.Mode != "raw" {`@18; fixed present `if p.Mode != "raw" {`@18 |
| q21 | behavior |  |  | behavior: vuln present `rows, err := db.Query(`@26; fixed present `rows, err := db.Query(`@26 |

### Scenario s5 (s5.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-200 Exposure of Sensitive Information.

#### vuln

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"fmt"
   5 | 	"net/http"
   6 | )
   7 | 
   8 | type Settings struct {
   9 | 	APIToken string
  10 | 	Version  string
  11 | }
  12 | 
  13 | func HandleStatus(w http.ResponseWriter, r *http.Request, st Settings) {
  14 | 	w.Header().Set("Content-Type", "text/plain")
  15 | 	fmt.Fprintf(w, "ok %s\n", r.URL.Path)
  16 | 	fmt.Fprintf(w, "token=%s\n", st.APIToken)
  17 | 	fmt.Fprintf(w, "version=%s\n", st.Version)
  18 | }
```

#### fixed

```go
   1 | package scen
   2 | 
   3 | import (
   4 | 	"fmt"
   5 | 	"net/http"
   6 | )
   7 | 
   8 | type Settings struct {
   9 | 	APIToken string
  10 | 	Version  string
  11 | }
  12 | 
  13 | func HandleStatus(w http.ResponseWriter, r *http.Request, st Settings) {
  14 | 	w.Header().Set("Content-Type", "text/plain")
  15 | 	fmt.Fprintf(w, "ok %s\n", r.URL.Path)
  16 | 	fmt.Fprintf(w, "version=%s\n", st.Version)
  17 | }
```

#### diff

```diff
--- vuln/s5.go
+++ fixed/s5.go
@@ -13,6 +13,5 @@
 func HandleStatus(w http.ResponseWriter, r *http.Request, st Settings) {
 	w.Header().Set("Content-Type", "text/plain")
 	fmt.Fprintf(w, "ok %s\n", r.URL.Path)
-	fmt.Fprintf(w, "token=%s\n", st.APIToken)
 	fmt.Fprintf(w, "version=%s\n", st.Version)
 }
```

| id | role | kind | semantic | realization per revision |
|---|---|---|---|---|
| q22 | behavior |  |  | behavior: vuln present `fmt.Fprintf(w, "token=%s\n", st.APIToken)`@16; fixed present `fmt.Fprintf(w, "version=%s\n", st.Version)`@16 |
| q23 | behavior |  |  | behavior: vuln present `fmt.Fprintf(w, "token=%s\n", st.APIToken)`@16; fixed absent (context `fmt.Fprintf(w, "ok %s\n", r.URL.Path)`@15) |
| q24 | entry |  |  | entry: vuln present `r *http.Request`@13; fixed present `r *http.Request`@13 |
| q25 | behavior |  |  | behavior: vuln present `fmt.Fprintf(w, "token=%s\n", st.APIToken)`@16; fixed absent (context `fmt.Fprintf(w, "version=%s\n", st.Version)`@16) |

### Scenario s7 (s7.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

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
| q28 | entry |  |  | entry: vuln present `raw := r.URL.Query().Get("p")`@12; fixed present `raw := r.URL.Query().Get("p")`@12 |
| q29 | behavior |  |  | behavior: vuln present `if strings.Contains(raw, "..") {`@13; fixed present `if strings.Contains(name, "..") {`@18 |

### Scenario s8 (s8.go)

**Claim:** In package scen, attacker-controlled input may lead to CWE-22 Path Traversal.

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
| q31 | entry |  |  | entry: vuln present `key := r.URL.Query().Get("key")`@16; fixed present `key := r.URL.Query().Get("key")`@20 |
| q32 | qualifier | guard | expected: must_not_hold | subject: vuln present `u Uploader`@15; fixed present `u Uploader`@15<br>predicate: vuln absent (context `key := r.URL.Query().Get("key")`@16); fixed present `if !u.Verified {`@16 |
| q33 | behavior |  |  | behavior: vuln present `if strings.HasPrefix(key, "/") {`@17; fixed present `if strings.HasPrefix(key, "/") || strings.Contains(key, "..") {`@21 |
| q34 | behavior |  |  | behavior: vuln absent (context `key := r.URL.Query().Get("key")`@16); fixed present `if !u.Verified {`@16 |
| q35 | qualifier | guard | expected: must_not_hold | subject: vuln present `u Uploader`@15; fixed present `u Uploader`@15<br>predicate: vuln absent (context `if strings.HasPrefix(key, "/") {`@17); fixed present `if !u.Verified {`@16 |

### Scenario s4 (s4.py)

**Claim:** In package s4, attacker-controlled input may lead to CWE-347 Improper Verification of Cryptographic Signature.

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
| q37 | entry |  |  | entry: vuln present `header, msg, sig, key`@19; fixed present `header, msg, sig, key`@19 |
| q38 | behavior |  |  | behavior: vuln present `ALGS = {"none": NoneAlg(), "HS256": HmacAlg()}`@16; fixed present `ALGS = {"HS256": HmacAlg()}`@16 |
| q39 | entry |  |  | entry: vuln present `name = header["alg"]`@20; fixed present `name = header["alg"]`@20 |
| q40 | qualifier | dispatch_target |  | call: vuln present `alg.verify(msg, sig, key)`@22; fixed present `alg.verify(msg, sig, key)`@22<br>target: vuln present `def verify(self, msg, sig, key):`@12; fixed present `def verify(self, msg, sig, key):`@12 |
| q41 | behavior |  |  | behavior: vuln present `return sig == b""`@8; fixed present `return sig == b""`@8 |

### Scenario s6 (s6.py)

**Claim:** In package s6, attacker-controlled input may lead to CWE-22 Path Traversal.

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
| q42 | entry |  |  | entry: vuln present `user_path`@5; fixed present `user_path`@5 |
| q43 | entry |  |  | entry: vuln present `full = os.path.normpath(os.path.join(base, user_path))`@6; fixed present `full = os.path.normpath(os.path.join(base, user_path))`@6 |
| q44 | behavior |  |  | behavior: vuln present `if not full.startswith(base):`@7; fixed present `if os.path.commonpath([full, base]) != base:`@7 |
| q45 | qualifier | transform | expected: must_be_present | subject: vuln present `user_path`@5; fixed present `user_path`@5<br>transform: vuln present `full = os.path.normpath(os.path.join(base, user_path))`@6; fixed present `full = os.path.normpath(os.path.join(base, user_path))`@6 |
| q46 | behavior |  |  | behavior: vuln present `return full`@9; fixed present `return full`@9 |

## Output

Reply with YAML in exactly the form of the template (`rd-boundary-labels.template.yaml`): every id in Part 1 under `relations`, every id in Part 2 under `requirements`. Write every label and the date as a quoted string.
