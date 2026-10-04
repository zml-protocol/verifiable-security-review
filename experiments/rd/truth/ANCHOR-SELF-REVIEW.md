# Author anchor self-review (authoring discipline, NOT a protocol change)

A fixed checklist the author runs on a fixture's `requirement-truth.yaml` **before any judge sees
the bundle**, using only the already-frozen `definitions.yaml`. It adds no scoring rule and changes
no frozen measurement rule; it only reduces avoidable author anchor-granularity errors (which cost
two Go reserves — oh-my-posh entry, fabric-ca context). Run it, tick every line, then freeze the
author truth; once Judge A or B has seen the material the author truth is immutable (a
granularity error then stands as INDETERMINATE/inadmissible — there is no post-adjudication fix).

Order (strict): author draft → this self-review against frozen definitions → freeze author truth
(the bundle hash) → Judge A / Judge B → reconciliation.

## Entry (EN-1/EN-2/EN-3)
- [ ] Anchored at the specific statement/parameter the EN rule names — NOT the whole function/FuncDecl.
- [ ] It is the first point the attacker-controlled value enters code — not a later derived value (EN-3),
      not a broader node than the actual extraction.

## Behavior (BE-1/BE-2/BE-3)
- [ ] Chosen strictly by BE-1/BE-2/BE-3.
- [ ] If a changed check/transform: it is the one **nearest the effect that directly decides the effect**
      for the triggering input — not merely the most visible line in the diff.
- [ ] If two changed checks on different branches each decide the effect and cannot be ordered → it is
      INDETERMINATE (do not force a pick).

## Absent context (AC-1/AC-2/AC-3)
- [ ] The **statement** the absent element would protect/feed (AC-1/AC-2) or the diff-aligned statement
      after the insertion/removal point (AC-3).
- [ ] NOT a sub-expression / argument inside that statement; NOT the whole enclosing function/block.

## Qualifier (if any)
- [ ] `kind` is actually in the frozen vocabulary (`guard`/`config`/`dispatch_target`); `transform` and
      unknown kinds are a vocabulary blind spot, not a qualifier.
- [ ] subject/predicate/config/target anchors are at the syntactic level the definition requires.
- [ ] A security-related but NOT claim-necessary change is a non-scored note, not a forced qualifier.

## Matcher sanity (frozen resolver/matcher)
- [ ] Every anchor resolves **uniquely** via the frozen resolver (run it).
- [ ] The `expression` corresponds exactly to the intended node — not a wide span that merely *contains*
      it (no "function-level anchor happens to include the target statement, so it counts").
- [ ] Per-revision line numbers are correct (insertions shift lines).

## Record
- [ ] Self-review done and every box ticked before the bundle was built / any judge invoked.
