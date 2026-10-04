/**
 * Node kinds shared by the P-Hybrid-1 Go hop verifiers (PREREGISTRATION.md §10).
 * Nothing here names a fixture, a file or a symbol of one.
 */

import go

/** The start of `n`, as the hop matcher expects it: file, line, column (1-based). */
predicate startOf(Locatable n, string file, int line, int col) {
  file = n.getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

/** A statement that defines local variables: `v := e`, `v = e`, `var v = e`. */
class Definition extends AstNode {
  Definition() {
    this.(Assignment).getAnLhs().(Ident).refersTo(any(LocalVariable v))
    or
    this.(ValueSpec).getANameExpr().refersTo(any(LocalVariable v)) and
    exists(this.(ValueSpec).getAnInit())
  }

  /** The SSA definition this statement makes of `v`. */
  SsaExplicitDefinition getSsaDefinition() {
    exists(int i |
      result.getInstruction() = IR::assignInstruction(this, i) or
      result.getInstruction() = IR::initInstruction(this, i)
    )
  }
}

/** A store into one field: `x.f = e` (including `x.f = append(x.f, ...)`). */
class FieldStore extends Assignment {
  FieldStore() {
    this.getNumLhs() = 1 and
    this.getLhs().(SelectorExpr).getSelector().refersTo(any(Field f))
  }

  SelectorExpr getTarget() { result = this.getLhs() }

  /** The expressions this store puts into the field; `append(x.f, a, b)` stores `a` and `b`. */
  Expr getAStoredExpr() {
    exists(CallExpr app | app = this.getRhs() and app.getTarget() = Builtin::append() |
      result = app.getArgument(any(int i | i > 0))
    )
    or
    not exists(CallExpr app | app = this.getRhs() and app.getTarget() = Builtin::append()) and
    result = this.getRhs()
  }

  /** The variable whose field is stored into, when the base is a plain variable. */
  Ident getBase() { result = this.getTarget().getBase() }
}

/** An explicit field of a struct literal: `f: e`. */
class KeyedField extends KeyValueExpr {
  KeyedField() { this.getLiteral() instanceof StructLit }
}

/** `inner` is `outer` or sits inside it through literal elements, keyed values, `&` and parens. */
predicate literalPart(Expr outer, Expr inner) {
  inner = outer
  or
  exists(Expr mid | literalPart(outer, mid) |
    inner = mid.(CompositeLit).getAnElement()
    or
    inner = mid.(KeyValueExpr).getValue()
    or
    inner = mid.(AddressExpr).getOperand()
    or
    inner = mid.(ParenExpr).getExpr()
  )
}

/** `e` is `root` or any expression below it. */
predicate within(Expr root, Expr e) { e = root or e.getParent+() = root }
