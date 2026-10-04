# RD requirement-truth adjudication — your task

You are one of two INDEPENDENT truth adjudicators for a single security-fix fixture. Work only from
the material in THIS message. Do not use outside knowledge of the project or repository. Produce only
the YAML output described at the end.

## Claim and domain
Claim: in package `ldap`, attacker-controlled input (an authentication username containing LDAP
filter metacharacters such as *, (, ), \) may lead to LDAP injection (CWE injection): the username is
interpolated into the LDAP search filter unescaped, so a metacharacter changes the filter's meaning
(e.g. * becomes a wildcard).
Domain: the attacker controls the username presented for the LDAP user lookup; every other state may
take any value the code allows.

## What you decide
For EVERY item in the adjudication sheet below, decide whether it is REQUIRED, NOT_REQUIRED, or
INDETERMINATE for the claim, judged against the operational definitions.
- REQUIRED = for the claim to hold, this exact requirement (its kind, its per-revision present/absent
  state, and its anchored program points) must be true.
- Judge each item INDEPENDENTLY. Do NOT label an item REQUIRED merely because the fix touches that code.
- INDETERMINATE = the definitions do not decide it on the evidence given.
- The two revisions are labelled `vuln` and `fixed`; you may use the fix diff and the observed
  execution facts as evidence.
- You MAY also list requirement items you believe are required but missing from the sheet, in the
  requirement schema (kind + per-revision anchors {file,start_line,end_line,expression}).

The exact output schema is at the very end of this message.


========================================================================
# OPERATIONAL DEFINITIONS (frozen)
```yaml
# RD operational definitions (PREREGISTRATION.md §15.1, §15.3, §15.4). Version 2, the one-time
# revision after decidability round 1 (claim domain and QU-1 only). Frozen (Codex approved, 2026-10-01).
# Shown verbatim to the adjudicators, who label the synthetic boundary cases against it. Each
# boundary rule has an id; every boundary case names the rule it tests. Nothing here refers to
# any fixture. Relation names and endpoint kinds are the frozen ones (hop_verify/relations.yaml,
# hop_bridge/relations.yaml); the definitions make their boundaries explicit.
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

========================================================================
# ADVISORY — FACTUAL EVIDENCE

# Advisory factual evidence — GHSA-xghw-p77p-3r7x

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-xghw-p77p-3r7x  (aliases: CVE-2026-53658, GO-2026-6234)
- Affected package: Go: github.com/hyperledger/fabric-ca
- Severity: CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N
- Published: 2026-08-14T19:24:57Z
- Summary: Fabric CA Developer's Guide: LDAP Injection via Unescaped Username in GetUser Filter
- Source: https://github.com/hyperledger/fabric-ca/security/advisories/GHSA-xghw-p77p-3r7x

## Details (verbatim, fix-attribution lines removed)

When fabric-ca is configured with an LDAP backend, the username from HTTP Basic authentication is included in an LDAP uid search filter without proper escaping. An unauthenticated attacker with network access to the CA enrollment endpoint could exploit this to perform LDAP injection before password validation, and potentially steer authentication attempts toward a victim account.

### Recommendation

- All users of fabric-ca with an LDAP backend should update to a fixed version.
- For users not using an LDAP backend, no action is required.

## References (fix-commit excluded)
- WEB: https://github.com/hyperledger/fabric-ca/security/advisories/GHSA-xghw-p77p-3r7x
- PACKAGE: https://github.com/hyperledger/fabric-ca

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.

========================================================================
# EXECUTION EVIDENCE (observed facts)

# Execution evidence (observed facts) — GHSA-xghw-p77p-3r7x

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input: `Client.GetUser("rd*probe", ...)` — a username containing an LDAP filter metacharacter (`*`),
  looked up against an identical local capture server on both revisions.
- Method: the same probe on both revisions captures the emitted LDAP SearchRequest (BER bytes); the
  fix commit's test (`TestUsernameEscape`) also applied to both (go1.26.8, `-mod=readonly`).

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| emitted LDAP filter for `rd*probe` | wildcard substring filter: `initial "rd"` + `any "probe"` (`(uid=rd*probe)`, `*` interpreted as a wildcard) | equality match on the literal value `rd*probe` (no wildcard structure) |

Same input, the `*` is interpreted as a filter wildcard on the vuln revision and as a literal on the
fixed revision.

========================================================================
# FIX DIFF (vuln -> fixed)

```diff
diff --git a/lib/server/ldap/client.go b/lib/server/ldap/client.go
index 7502ea4..a77a956 100644
--- a/lib/server/ldap/client.go
+++ b/lib/server/ldap/client.go
@@ -141,6 +141,14 @@ func cfgVal(val1, val2 string) string {
 	return val2
 }
 
+// Connection to an LDAP server.
+type Connection interface {
+	// Search using the given search request.
+	Search(searchRequest *ldap.SearchRequest) (*ldap.SearchResult, error)
+	// Close the connection.
+	Close() error
+}
+
 // Client is an LDAP client
 type Client struct {
 	Host          string
@@ -154,7 +162,7 @@ type Client struct {
 	attrNames     []string             // Names of attributes to request on an LDAP search
 	attrExprs     map[string]*userExpr // Expressions to evaluate to get attribute value
 	attrMaps      map[string]map[string]string
-	AdminConn     *ldap.Conn
+	AdminConn     Connection
 	TLS           *ctls.ClientTLSConfig
 	CSP           bccsp.BCCSP
 }
@@ -169,10 +177,11 @@ func (lc *Client) GetUser(username string, attrNames []string) (causer.User, err
 	log.Debugf("Getting user '%s'", username)
 
 	// Search for the given username
+	escapedUsername := ldap.EscapeFilter(username)
 	sreq := ldap.NewSearchRequest(
 		lc.Base, ldap.ScopeWholeSubtree,
 		ldap.NeverDerefAliases, 0, 0, false,
-		fmt.Sprintf(lc.UserFilter, username),
+		fmt.Sprintf(lc.UserFilter, escapedUsername),
 		lc.attrNames,
 		nil,
 	)
@@ -297,7 +306,7 @@ func (lc *Client) newConnection() (conn *ldap.Conn, err error) {
 	address := fmt.Sprintf("%s:%d", lc.Host, lc.Port)
 	if !lc.UseSSL {
 		log.Debug("Connecting to LDAP server over TCP")
-		conn, err = ldap.Dial("tcp", address)
+		conn, err = ldap.DialURL("ldap://" + address)
 		if err != nil {
 			return conn, errors.Wrapf(err, "Failed to connect to LDAP server over TCP at %s", address)
 		}
@@ -310,7 +319,7 @@ func (lc *Client) newConnection() (conn *ldap.Conn, err error) {
 
 		tlsConfig.ServerName = lc.Host
 
-		conn, err = ldap.DialTLS("tcp", address, tlsConfig)
+		conn, err = ldap.DialURL("ldaps://"+address, ldap.DialWithTLSConfig(tlsConfig))
 		if err != nil {
 			return conn, errors.Wrapf(err, "Failed to connect to LDAP server over TLS at %s", address)
 		}
```

========================================================================

# Code context — vuln revision


## lib/server/ldap/client.go (lines 144-205)

```go
 144  // Client is an LDAP client
 145  type Client struct {
 146  	Host          string
 147  	Port          int
 148  	UseSSL        bool
 149  	AdminDN       string
 150  	AdminPassword string
 151  	Base          string
 152  	UserFilter    string               // e.g. "(uid=%s)"
 153  	GroupFilter   string               // e.g. "(memberUid=%s)"
 154  	attrNames     []string             // Names of attributes to request on an LDAP search
 155  	attrExprs     map[string]*userExpr // Expressions to evaluate to get attribute value
 156  	attrMaps      map[string]map[string]string
 157  	AdminConn     *ldap.Conn
 158  	TLS           *ctls.ClientTLSConfig
 159  	CSP           bccsp.BCCSP
 160  }
 161  
 162  // GetUser returns a user object for username and attribute values
 163  // for the requested attribute names
 164  func (lc *Client) GetUser(username string, attrNames []string) (causer.User, error) {
 165  
 166  	var sresp *ldap.SearchResult
 167  	var err error
 168  
 169  	log.Debugf("Getting user '%s'", username)
 170  
 171  	// Search for the given username
 172  	sreq := ldap.NewSearchRequest(
 173  		lc.Base, ldap.ScopeWholeSubtree,
 174  		ldap.NeverDerefAliases, 0, 0, false,
 175  		fmt.Sprintf(lc.UserFilter, username),
 176  		lc.attrNames,
 177  		nil,
 178  	)
 179  
 180  	// Try to search using the cached connection, if there is one
 181  	conn := lc.AdminConn
 182  	if conn != nil {
 183  		log.Debugf("Searching for user '%s' using cached connection", username)
 184  		sresp, err = conn.Search(sreq)
 185  		if err != nil {
 186  			log.Debugf("LDAP search failed but will close connection and try again; error was: %s", err)
 187  			conn.Close()
 188  			lc.AdminConn = nil
 189  		}
 190  	}
 191  
 192  	// If there was no cached connection or the search failed for any reason
 193  	// (including because the server may have closed the cached connection),
 194  	// try with a new connection.
 195  	if sresp == nil {
 196  		log.Debugf("Searching for user '%s' using new connection", username)
 197  		conn, err = lc.newConnection()
 198  		if err != nil {
 199  			return nil, err
 200  		}
 201  		sresp, err = conn.Search(sreq)
 202  		if err != nil {
 203  			conn.Close()
 204  			return nil, errors.Wrapf(err, "LDAP search failure; search request: %+v", sreq)
 205  		}
```

========================================================================

# Code context — fixed revision


## lib/server/ldap/client.go (lines 144-205)

```go
 144  // Connection to an LDAP server.
 145  type Connection interface {
 146  	// Search using the given search request.
 147  	Search(searchRequest *ldap.SearchRequest) (*ldap.SearchResult, error)
 148  	// Close the connection.
 149  	Close() error
 150  }
 151  
 152  // Client is an LDAP client
 153  type Client struct {
 154  	Host          string
 155  	Port          int
 156  	UseSSL        bool
 157  	AdminDN       string
 158  	AdminPassword string
 159  	Base          string
 160  	UserFilter    string               // e.g. "(uid=%s)"
 161  	GroupFilter   string               // e.g. "(memberUid=%s)"
 162  	attrNames     []string             // Names of attributes to request on an LDAP search
 163  	attrExprs     map[string]*userExpr // Expressions to evaluate to get attribute value
 164  	attrMaps      map[string]map[string]string
 165  	AdminConn     Connection
 166  	TLS           *ctls.ClientTLSConfig
 167  	CSP           bccsp.BCCSP
 168  }
 169  
 170  // GetUser returns a user object for username and attribute values
 171  // for the requested attribute names
 172  func (lc *Client) GetUser(username string, attrNames []string) (causer.User, error) {
 173  
 174  	var sresp *ldap.SearchResult
 175  	var err error
 176  
 177  	log.Debugf("Getting user '%s'", username)
 178  
 179  	// Search for the given username
 180  	escapedUsername := ldap.EscapeFilter(username)
 181  	sreq := ldap.NewSearchRequest(
 182  		lc.Base, ldap.ScopeWholeSubtree,
 183  		ldap.NeverDerefAliases, 0, 0, false,
 184  		fmt.Sprintf(lc.UserFilter, escapedUsername),
 185  		lc.attrNames,
 186  		nil,
 187  	)
 188  
 189  	// Try to search using the cached connection, if there is one
 190  	conn := lc.AdminConn
 191  	if conn != nil {
 192  		log.Debugf("Searching for user '%s' using cached connection", username)
 193  		sresp, err = conn.Search(sreq)
 194  		if err != nil {
 195  			log.Debugf("LDAP search failed but will close connection and try again; error was: %s", err)
 196  			conn.Close()
 197  			lc.AdminConn = nil
 198  		}
 199  	}
 200  
 201  	// If there was no cached connection or the search failed for any reason
 202  	// (including because the server may have closed the cached connection),
 203  	// try with a new connection.
 204  	if sresp == nil {
 205  		log.Debugf("Searching for user '%s' using new connection", username)
```

========================================================================
# ADJUDICATION SHEET — the items you must label

```yaml
fixture: GHSA-xghw-p77p-3r7x
revisions:
- vuln
- fixed
instructions: Label each item REQUIRED / NOT_REQUIRED / INDETERMINATE against the
  frozen definitions and the code context. You may add a missing required item in
  the frozen requirement schema (kind + per-revision anchors).
items:
- id: item-01
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 175
        end_line: 175
        expression: fmt.Sprintf(lc.UserFilter, username),
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 141
        end_line: 141
        expression: return val2
- id: item-02
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 175
        end_line: 175
        expression: fmt.Sprintf(lc.UserFilter, username),
    fixed:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 180
        end_line: 180
        expression: escapedUsername := ldap.EscapeFilter(username)
- id: item-03
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 175
        end_line: 175
        expression: fmt.Sprintf(lc.UserFilter, username),
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 180
        end_line: 180
        expression: escapedUsername := ldap.EscapeFilter(username)
- id: item-04
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 141
        end_line: 141
        expression: return val2
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 141
        end_line: 141
        expression: return val2
- id: item-05
  kind: entry
  entry:
    vuln:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 164
        end_line: 164
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 172
        end_line: 172
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
- id: item-06
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 164
        end_line: 164
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
    fixed:
      state: absent
      context:
        file: lib/server/ldap/client.go
        start_line: 172
        end_line: 172
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
- id: item-07
  kind: behavior
  behavior:
    vuln:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 175
        end_line: 175
        expression: fmt.Sprintf(lc.UserFilter, username),
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 180
        end_line: 180
        expression: escapedUsername := ldap.EscapeFilter(username)
- id: item-08
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 164
        end_line: 164
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
    fixed:
      state: present
      anchor:
        file: lib/server/ldap/client.go
        start_line: 172
        end_line: 172
        expression: func (lc *Client) GetUser(username string, attrNames []string)
          (causer.User, error) {
```

========================================================================
# YOUR OUTPUT — reply with ONLY this YAML, nothing else

```yaml
labels:
  item-01: REQUIRED
  item-02: NOT_REQUIRED
  # ... one line for EVERY item id present in the sheet ...
missing:
  - kind: behavior
    behavior:
      vuln:  {state: absent,  context: {file: "...", start_line: 0, end_line: 0, expression: "..."}}
      fixed: {state: present, anchor:  {file: "...", start_line: 0, end_line: 0, expression: "..."}}
```

Give a label for every item id in the sheet; `expression` must be the exact source line(s); no prose
outside the YAML.
