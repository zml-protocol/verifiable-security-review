# RD requirement-truth adjudication — your task

You are one of two INDEPENDENT truth adjudicators for a single security-fix fixture. Work only from
the material in THIS message. Do not use outside knowledge of the project or repository. Produce only
the YAML output described at the end.

## Claim and domain
Claim: in package `nclient4`, attacker-controlled input (a crafted UDP/IPv4 frame whose declared IP
payload length is smaller than a UDP header) may lead to an out-of-bounds slice with a negative
length, causing a reachable runtime panic (denial of service) while reading from BroadcastRawUDPConn.
Domain: the attacker controls the bytes delivered to the raw packet connection (the received frame);
every other state may take any value the code allows.

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

# Advisory factual evidence — GO-2026-6237

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GO-2026-6237  (aliases: )
- Affected package: Go: github.com/insomniacslk/dhcp
- Severity: 
- Published: 2026-08-18T16:38:10Z
- Summary: Denial of service via malformed IPv4 packet in github.com/insomniacslk/dhcp
- Source: https://github.com/insomniacslk/dhcp/commit/c76316d4aa825673b208730779843d0711021e81

## Details (verbatim, fix-attribution lines removed)

In github.com/insomniacslk/dhcp/dhcpv4/nclient4, BroadcastRawUDPConn.ReadFrom does not validate that the IPv4 payload length is sufficient to hold a UDP header before calculating the DHCP payload length. A frame with an IPv4 total-length field specifying fewer than eight payload bytes results in a negative DHCP length, causing a panic in buf.Consume due to a negative slice bound.

## References (fix-commit excluded)

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.

========================================================================
# EXECUTION EVIDENCE (observed facts)

# Execution evidence (observed facts) — GO-2026-6237

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input: a UDP/IPv4 frame delivered to `BroadcastRawUDPConn` whose IPv4 header declares an IP payload
  length smaller than a UDP header (8 bytes) — e.g. a declared payload length of 0.
- Method: the fix commit's regression test applied to both revisions (go1.26.8, `-mod=readonly`),
  `go test ./dhcpv4/nclient4/...`.

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| short-IP-payload frame | test exits non-zero: panic `slice bounds out of range [:-8]` in `buf.Consume` | test passes: the short frame is discarded and reading continues |

Same input, the panic occurs on the vuln revision and not on the fixed revision.

========================================================================
# FIX DIFF (vuln -> fixed)

```diff
diff --git a/dhcpv4/nclient4/conn_unix.go b/dhcpv4/nclient4/conn_unix.go
index f3e48c6..51b93e6 100644
--- a/dhcpv4/nclient4/conn_unix.go
+++ b/dhcpv4/nclient4/conn_unix.go
@@ -111,6 +111,14 @@ func (upc *BroadcastRawUDPConn) ReadFrom(b []byte) (int, net.Addr, error) {
 			continue
 		}
 
+		// The IPv4 payload must be large enough to hold a UDP header. Discarding
+		// frames that declare fewer bytes keeps the DHCP length computed below
+		// non-negative and avoids parsing trailing padding as a UDP header.
+		ipPayloadLen := int(ipHdr.payloadLength())
+		if ipPayloadLen < udpHdrLen {
+			continue
+		}
+
 		if !buf.Has(udpHdrLen) {
 			continue
 		}
@@ -128,9 +136,12 @@ func (upc *BroadcastRawUDPConn) ReadFrom(b []byte) (int, net.Addr, error) {
 			IP:   ipHdr.sourceAddress(),
 			Port: int(udpHdr.sourcePort()),
 		}
-		// Extra padding after end of IP packet should be ignored,
-		// if not dhcp option parsing will fail.
-		dhcpLen := int(ipHdr.payloadLength()) - udpHdrLen
+		// Extra padding after the end of the IP payload is ignored; otherwise
+		// dhcp option parsing would fail.
+		dhcpLen := ipPayloadLen - udpHdrLen
+		if !buf.Has(dhcpLen) {
+			continue
+		}
 		return copy(b, buf.Consume(dhcpLen)), srcAddr, nil
 	}
 }
```

========================================================================

# Code context — vuln revision


## dhcpv4/nclient4/conn_unix.go (lines 72-143)

```go
  72  func udpMatch(addr *net.UDPAddr, bound *net.UDPAddr) bool {
  73  	if bound == nil {
  74  		return true
  75  	}
  76  	if bound.IP != nil && !bound.IP.Equal(addr.IP) {
  77  		return false
  78  	}
  79  	return bound.Port == addr.Port
  80  }
  81  
  82  // ReadFrom implements net.PacketConn.ReadFrom.
  83  //
  84  // ReadFrom reads raw IP packets and will try to match them against
  85  // upc.boundAddr. Any matching packets are returned via the given buffer.
  86  func (upc *BroadcastRawUDPConn) ReadFrom(b []byte) (int, net.Addr, error) {
  87  	ipHdrMaxLen := ipv4MaximumHeaderSize
  88  	udpHdrLen := udpMinimumSize
  89  
  90  	for {
  91  		pkt := make([]byte, ipHdrMaxLen+udpHdrLen+len(b))
  92  		n, _, err := upc.PacketConn.ReadFrom(pkt)
  93  		if err != nil {
  94  			return 0, nil, err
  95  		}
  96  		if n == 0 {
  97  			return 0, nil, io.EOF
  98  		}
  99  		pkt = pkt[:n]
 100  		buf := uio.NewBigEndianBuffer(pkt)
 101  
 102  		ipHdr := ipv4(buf.Data())
 103  
 104  		if !ipHdr.isValid(n) {
 105  			continue
 106  		}
 107  
 108  		ipHdr = ipv4(buf.Consume(int(ipHdr.headerLength())))
 109  
 110  		if ipHdr.transportProtocol() != udpProtocolNumber {
 111  			continue
 112  		}
 113  
 114  		if !buf.Has(udpHdrLen) {
 115  			continue
 116  		}
 117  
 118  		udpHdr := udp(buf.Consume(udpHdrLen))
 119  
 120  		addr := &net.UDPAddr{
 121  			IP:   ipHdr.destinationAddress(),
 122  			Port: int(udpHdr.destinationPort()),
 123  		}
 124  		if !udpMatch(addr, upc.boundAddr) {
 125  			continue
 126  		}
 127  		srcAddr := &net.UDPAddr{
 128  			IP:   ipHdr.sourceAddress(),
 129  			Port: int(udpHdr.sourcePort()),
 130  		}
 131  		// Extra padding after end of IP packet should be ignored,
 132  		// if not dhcp option parsing will fail.
 133  		dhcpLen := int(ipHdr.payloadLength()) - udpHdrLen
 134  		return copy(b, buf.Consume(dhcpLen)), srcAddr, nil
 135  	}
 136  }
 137  
 138  // WriteTo implements net.PacketConn.WriteTo and broadcasts all packets at the
 139  // raw socket level.
 140  //
 141  // WriteTo wraps the given packet in the appropriate UDP and IP header before
 142  // sending it on the packet conn.
 143  func (upc *BroadcastRawUDPConn) WriteTo(b []byte, addr net.Addr) (int, error) {
```

========================================================================

# Code context — fixed revision


## dhcpv4/nclient4/conn_unix.go (lines 72-143)

```go
  72  func udpMatch(addr *net.UDPAddr, bound *net.UDPAddr) bool {
  73  	if bound == nil {
  74  		return true
  75  	}
  76  	if bound.IP != nil && !bound.IP.Equal(addr.IP) {
  77  		return false
  78  	}
  79  	return bound.Port == addr.Port
  80  }
  81  
  82  // ReadFrom implements net.PacketConn.ReadFrom.
  83  //
  84  // ReadFrom reads raw IP packets and will try to match them against
  85  // upc.boundAddr. Any matching packets are returned via the given buffer.
  86  func (upc *BroadcastRawUDPConn) ReadFrom(b []byte) (int, net.Addr, error) {
  87  	ipHdrMaxLen := ipv4MaximumHeaderSize
  88  	udpHdrLen := udpMinimumSize
  89  
  90  	for {
  91  		pkt := make([]byte, ipHdrMaxLen+udpHdrLen+len(b))
  92  		n, _, err := upc.PacketConn.ReadFrom(pkt)
  93  		if err != nil {
  94  			return 0, nil, err
  95  		}
  96  		if n == 0 {
  97  			return 0, nil, io.EOF
  98  		}
  99  		pkt = pkt[:n]
 100  		buf := uio.NewBigEndianBuffer(pkt)
 101  
 102  		ipHdr := ipv4(buf.Data())
 103  
 104  		if !ipHdr.isValid(n) {
 105  			continue
 106  		}
 107  
 108  		ipHdr = ipv4(buf.Consume(int(ipHdr.headerLength())))
 109  
 110  		if ipHdr.transportProtocol() != udpProtocolNumber {
 111  			continue
 112  		}
 113  
 114  		// The IPv4 payload must be large enough to hold a UDP header. Discarding
 115  		// frames that declare fewer bytes keeps the DHCP length computed below
 116  		// non-negative and avoids parsing trailing padding as a UDP header.
 117  		ipPayloadLen := int(ipHdr.payloadLength())
 118  		if ipPayloadLen < udpHdrLen {
 119  			continue
 120  		}
 121  
 122  		if !buf.Has(udpHdrLen) {
 123  			continue
 124  		}
 125  
 126  		udpHdr := udp(buf.Consume(udpHdrLen))
 127  
 128  		addr := &net.UDPAddr{
 129  			IP:   ipHdr.destinationAddress(),
 130  			Port: int(udpHdr.destinationPort()),
 131  		}
 132  		if !udpMatch(addr, upc.boundAddr) {
 133  			continue
 134  		}
 135  		srcAddr := &net.UDPAddr{
 136  			IP:   ipHdr.sourceAddress(),
 137  			Port: int(udpHdr.sourcePort()),
 138  		}
 139  		// Extra padding after the end of the IP payload is ignored; otherwise
 140  		// dhcp option parsing would fail.
 141  		dhcpLen := ipPayloadLen - udpHdrLen
 142  		if !buf.Has(dhcpLen) {
 143  			continue
```

========================================================================
# ADJUDICATION SHEET — the items you must label

```yaml
fixture: GO-2026-6237
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
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 114
        end_line: 114
        expression: if !buf.Has(udpHdrLen) {
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 118
        end_line: 118
        expression: if ipPayloadLen < udpHdrLen {
- id: item-02
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 114
        end_line: 114
        expression: if !buf.Has(udpHdrLen) {
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 118
        end_line: 118
        expression: if ipPayloadLen < udpHdrLen {
- id: item-03
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 93
        end_line: 93
        expression: if err != nil {
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 93
        end_line: 93
        expression: if err != nil {
- id: item-04
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 114
        end_line: 114
        expression: if !buf.Has(udpHdrLen) {
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 111
        end_line: 111
        expression: continue
- id: item-05
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 114
        end_line: 114
        expression: if !buf.Has(udpHdrLen) {
    fixed:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 118
        end_line: 118
        expression: if ipPayloadLen < udpHdrLen {
- id: item-06
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
- id: item-07
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
    fixed:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
- id: item-08
  kind: entry
  entry:
    vuln:
      state: absent
      context:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
    fixed:
      state: present
      anchor:
        file: dhcpv4/nclient4/conn_unix.go
        start_line: 92
        end_line: 92
        expression: n, _, err := upc.PacketConn.ReadFrom(pkt)
```

========================================================================
# YOUR OUTPUT — reply with ONLY this YAML, nothing else

```yaml
labels:
  item-01: REQUIRED        # exactly one line per item id in the sheet above
  item-02: NOT_REQUIRED    # one of: REQUIRED | NOT_REQUIRED | INDETERMINATE
  # ... one line for EVERY item id present in the sheet ...
missing:                   # optional; use [] if you propose none
  - kind: behavior
    behavior:
      vuln:  {state: absent,  context: {file: "...", start_line: 0, end_line: 0, expression: "..."}}
      fixed: {state: present, anchor:  {file: "...", start_line: 0, end_line: 0, expression: "..."}}
```

Give a label for every item id in the sheet; `expression` must be the exact source line(s) from the
code context; do not add any prose outside the YAML.
