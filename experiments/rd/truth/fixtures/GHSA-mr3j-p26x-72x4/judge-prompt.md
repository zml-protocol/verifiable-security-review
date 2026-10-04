# RD requirement-truth adjudication — your task

You are one of two INDEPENDENT truth adjudicators for a single security-fix fixture. Work only from
the material in THIS message. Do not use outside knowledge of the project or repository. Produce only
the YAML output described at the end.

## Claim and domain
Claim: in package `models`, attacker-controlled input may lead to CWE-862 Missing Authorization — a
task comment belonging to one task is read through a request that names a different task.
Domain: the attacker controls the HTTP request, including the task id and comment id path parameters.
Every other state (accounts, sessions, roles, configuration, environment, database contents) may take
any value the code allows.

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

# Advisory factual evidence — GHSA-mr3j-p26x-72x4

Mechanical, fact-only extract for adjudication. Fix-attribution lines are removed (logged
below); no hand paraphrase. The fix diff is supplied separately, not here.

- Advisory: GHSA-mr3j-p26x-72x4  (aliases: CVE-2026-33313, GO-2026-4797)
- Affected package: Go: code.vikunja.io/api
- Severity: CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N
- Published: 2026-03-20T17:25:30Z
- Summary: Vikunja has an IDOR in Task Comments Allows Reading Arbitrary Comments
- Source: https://github.com/go-vikunja/vikunja/security/advisories/GHSA-mr3j-p26x-72x4

## Details (verbatim, fix-attribution lines removed)

An authenticated user can read any task comment by ID, regardless of whether they have access to the task the comment belongs to, by substituting the task ID in the API URL with a task they do have access to.

## Details

The `GET /api/v1/tasks/{taskID}/comments/{commentID}` endpoint performs an authorization check against the task ID provided in the URL path, then loads the comment by its own ID without verifying it belongs to that task.

### Root Cause

In `pkg/models/task_comment_permissions.go`, `CanRead` constructs a `Task` using the `TaskID` from the URL and checks `Task.CanRead`:

```go
func (tc *TaskComment) CanRead(s *xorm.Session, a web.Auth) (bool, int, error) {
    t := Task{ID: tc.TaskID}
    return t.CanRead(s, a)
}
```

In `pkg/models/task_comments.go`, `getTaskCommentSimple` loads the comment by ID only, with `NoAutoCondition()` explicitly disabling XORM's implicit struct-field filtering:

```go
func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
    exists, err := s.
        Where("id = ?", tc.ID).
        NoAutoCondition().
        Get(tc)
    // ...
}
```

The generic web handler (`pkg/web/handler/read_one.go`) calls `CanRead` before `ReadOne`, so the permission check passes against the attacker-controlled task ID, and then `ReadOne` returns the comment from a completely different task.

### Attack Scenario

1. Attacker is authenticated and has read access to any task (task ID `A`) — e.g. their own task.
2. Attacker guesses or enumerates a comment ID (`C`) belonging to a task in another user's private project.
3. Attacker requests: `GET /api/v1/tasks/A/comments/C`
4. Authorization passes because the attacker can read task `A`.
5. The comment `C` is loaded by ID only and returned, leaking its contents and author.

## Credit

This vulnerability was found using [GitHub Security Lab Taskflows](https://github.com/GitHubSecurityLab/seclab-taskflows).

## References (fix-commit excluded)
- WEB: https://github.com/go-vikunja/vikunja/security/advisories/GHSA-mr3j-p26x-72x4
- ADVISORY: https://nvd.nist.gov/vuln/detail/CVE-2026-33313
- PACKAGE: https://github.com/go-vikunja/vikunja
- WEB: https://vikunja.io/changelog/vikunja-v2.2.0-was-released

## Redaction note
- 0 fix-attribution line(s) and 1 fix-locating reference(s) were removed so this evidence carries the vulnerability facts without the remediation answer.
- The verbatim removed lines are recorded author-side only (`advisory-redaction-log.md`), not in this judge bundle, to avoid leaking fix-attribution.

========================================================================
# EXECUTION EVIDENCE (observed facts)

# Execution evidence (observed facts) — GHSA-mr3j-p26x-72x4

Observed behaviour of the two revisions under one identical input. Facts only; no conclusion is
drawn about which program point is the entry or the behaviour.

- Input (one model call / request): `TaskComment.ReadOne` with `TaskID = 1`, `ID = 2`, where comment
  `2`'s real owning task is `2` (i.e. `GET /tasks/1/comments/2` for a comment that belongs to task 2).

Observed results:

| | vuln revision | fixed revision |
|---|---|---|
| `ReadOne(TaskID=1, ID=2)` | returns the comment owned by task 2, `err == nil` | returns `ErrTaskCommentDoesNotExist{ID: 2, TaskID: 1}`; no comment |

Same input, the comment is returned on the vuln revision and not on the fixed revision.

========================================================================
# FIX DIFF (vuln -> fixed)

```diff
diff --git a/pkg/models/task_comments.go b/pkg/models/task_comments.go
index 45f9f8f..648a6fc 100644
--- a/pkg/models/task_comments.go
+++ b/pkg/models/task_comments.go
@@ -196,6 +196,7 @@ func (tc *TaskComment) Update(s *xorm.Session, _ web.Auth) error {
 func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
 	exists, err := s.
 		Where("id = ?", tc.ID).
+		And("task_id = ?", tc.TaskID).
 		NoAutoCondition().
 		Get(tc)
 	if err != nil {
```

========================================================================

# Code context — vuln revision


## pkg/models/task_comments.go (lines 179-254)

```go
 179  	if err != nil {
 180  		return err
 181  	}
 182  
 183  	task, err := GetTaskSimple(s, &Task{ID: tc.TaskID})
 184  	if err != nil {
 185  		return err
 186  	}
 187  
 188  	events.DispatchOnCommit(s, &TaskCommentUpdatedEvent{
 189  		Task:    &task,
 190  		Comment: tc,
 191  		Doer:    tc.Author,
 192  	})
 193  	return nil
 194  }
 195  
 196  func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
 197  	exists, err := s.
 198  		Where("id = ?", tc.ID).
 199  		NoAutoCondition().
 200  		Get(tc)
 201  	if err != nil {
 202  		return err
 203  	}
 204  	if !exists {
 205  		return ErrTaskCommentDoesNotExist{
 206  			ID:     tc.ID,
 207  			TaskID: tc.TaskID,
 208  		}
 209  	}
 210  
 211  	return nil
 212  }
 213  
 214  // ReadOne handles getting a single comment
 215  // @Summary Remove a task comment
 216  // @Description Remove a task comment. The user doing this need to have at least read access to the task this comment belongs to.
 217  // @tags task
 218  // @Accept json
 219  // @Produce json
 220  // @Security JWTKeyAuth
 221  // @Param taskID path int true "Task ID"
 222  // @Param commentID path int true "Comment ID"
 223  // @Success 200 {object} models.TaskComment "The task comment object."
 224  // @Failure 400 {object} web.HTTPError "Invalid task comment object provided."
 225  // @Failure 404 {object} web.HTTPError "The task comment was not found."
 226  // @Failure 500 {object} models.Message "Internal error"
 227  // @Router /tasks/{taskID}/comments/{commentID} [get]
 228  func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err error) {
 229  	err = getTaskCommentSimple(s, tc)
 230  	if err != nil {
 231  		return err
 232  	}
 233  
 234  	// Get the author
 235  	author := &user.User{}
 236  	_, err = s.
 237  		Where("id = ?", tc.AuthorID).
 238  		Get(author)
 239  	tc.Author = author
 240  	return
 241  }
 242  
 243  // ReadAll returns all comments for a task
 244  // @Summary Get all task comments
 245  // @Description Get all task comments. The user doing this need to have at least read access to the task.
 246  // @tags task
 247  // @Accept json
 248  // @Produce json
 249  // @Security JWTKeyAuth
 250  // @Param taskID path int true "Task ID"
 251  // @Param order_by query string false "Sort order. Can be 'asc' for ascending or 'desc' for descending. Defaults to 'asc'."
 252  // @Success 200 {array} models.TaskComment "The array with all task comments"
 253  // @Failure 500 {object} models.Message "Internal error"
 254  // @Router /tasks/{taskID}/comments [get]
```

========================================================================

# Code context — fixed revision


## pkg/models/task_comments.go (lines 179-254)

```go
 179  	if err != nil {
 180  		return err
 181  	}
 182  
 183  	task, err := GetTaskSimple(s, &Task{ID: tc.TaskID})
 184  	if err != nil {
 185  		return err
 186  	}
 187  
 188  	events.DispatchOnCommit(s, &TaskCommentUpdatedEvent{
 189  		Task:    &task,
 190  		Comment: tc,
 191  		Doer:    tc.Author,
 192  	})
 193  	return nil
 194  }
 195  
 196  func getTaskCommentSimple(s *xorm.Session, tc *TaskComment) error {
 197  	exists, err := s.
 198  		Where("id = ?", tc.ID).
 199  		And("task_id = ?", tc.TaskID).
 200  		NoAutoCondition().
 201  		Get(tc)
 202  	if err != nil {
 203  		return err
 204  	}
 205  	if !exists {
 206  		return ErrTaskCommentDoesNotExist{
 207  			ID:     tc.ID,
 208  			TaskID: tc.TaskID,
 209  		}
 210  	}
 211  
 212  	return nil
 213  }
 214  
 215  // ReadOne handles getting a single comment
 216  // @Summary Remove a task comment
 217  // @Description Remove a task comment. The user doing this need to have at least read access to the task this comment belongs to.
 218  // @tags task
 219  // @Accept json
 220  // @Produce json
 221  // @Security JWTKeyAuth
 222  // @Param taskID path int true "Task ID"
 223  // @Param commentID path int true "Comment ID"
 224  // @Success 200 {object} models.TaskComment "The task comment object."
 225  // @Failure 400 {object} web.HTTPError "Invalid task comment object provided."
 226  // @Failure 404 {object} web.HTTPError "The task comment was not found."
 227  // @Failure 500 {object} models.Message "Internal error"
 228  // @Router /tasks/{taskID}/comments/{commentID} [get]
 229  func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err error) {
 230  	err = getTaskCommentSimple(s, tc)
 231  	if err != nil {
 232  		return err
 233  	}
 234  
 235  	// Get the author
 236  	author := &user.User{}
 237  	_, err = s.
 238  		Where("id = ?", tc.AuthorID).
 239  		Get(author)
 240  	tc.Author = author
 241  	return
 242  }
 243  
 244  // ReadAll returns all comments for a task
 245  // @Summary Get all task comments
 246  // @Description Get all task comments. The user doing this need to have at least read access to the task.
 247  // @tags task
 248  // @Accept json
 249  // @Produce json
 250  // @Security JWTKeyAuth
 251  // @Param taskID path int true "Task ID"
 252  // @Param order_by query string false "Sort order. Can be 'asc' for ascending or 'desc' for descending. Defaults to 'asc'."
 253  // @Success 200 {array} models.TaskComment "The array with all task comments"
 254  // @Failure 500 {object} models.Message "Internal error"
```

========================================================================
# ADJUDICATION SHEET — the items you must label

```yaml
fixture: GHSA-mr3j-p26x-72x4
revisions:
- vuln
- fixed
instructions: Label each item REQUIRED / NOT_REQUIRED / INDETERMINATE against the
  frozen definitions and the code context. You may add a missing required item in
  the frozen requirement schema (kind + per-revision anchors).
items:
- id: item-01
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 198
        end_line: 198
        expression: Where("id = ?", tc.ID).
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 198
        end_line: 198
        expression: Where("id = ?", tc.ID).
- id: item-02
  kind: entry
  entry:
    vuln:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 228
        end_line: 228
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 229
        end_line: 229
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
- id: item-03
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: NoAutoCondition().
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 198
        end_line: 198
        expression: Where("id = ?", tc.ID).
- id: item-04
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 228
        end_line: 228
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 229
        end_line: 229
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
- id: item-05
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: NoAutoCondition().
    fixed:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: And("task_id = ?", tc.TaskID).
- id: item-06
  kind: behavior
  behavior:
    vuln:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: NoAutoCondition().
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: And("task_id = ?", tc.TaskID).
- id: item-07
  kind: behavior
  behavior:
    vuln:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: NoAutoCondition().
    fixed:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 199
        end_line: 199
        expression: And("task_id = ?", tc.TaskID).
- id: item-08
  kind: entry
  entry:
    vuln:
      state: present
      anchor:
        file: pkg/models/task_comments.go
        start_line: 228
        end_line: 228
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
    fixed:
      state: absent
      context:
        file: pkg/models/task_comments.go
        start_line: 229
        end_line: 229
        expression: func (tc *TaskComment) ReadOne(s *xorm.Session, _ web.Auth) (err
          error) {
```

========================================================================
# YOUR OUTPUT — reply with ONLY this YAML, nothing else

```yaml
labels:
  item-01: REQUIRED        # exactly one line per item id in the sheet above
  item-02: NOT_REQUIRED    # one of: REQUIRED | NOT_REQUIRED | INDETERMINATE
  # ... one line for EVERY item id present in the sheet ...
missing:                   # optional; use [] if you propose none
  - kind: behavior         # entry | behavior | guard | config | dispatch_target
    behavior:
      vuln:  {state: absent,  context: {file: "...", start_line: 0, end_line: 0, expression: "..."}}
      fixed: {state: present, anchor:  {file: "...", start_line: 0, end_line: 0, expression: "..."}}
```

Give a label for every item id in the sheet; `expression` must be the exact source line(s) from the
code context; do not add any prose outside the YAML.
