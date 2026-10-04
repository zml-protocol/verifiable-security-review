/**
 * Node kinds shared by the §14 Python bridge verifier. Method-call kinds are the P-Hybrid-1
 * ones, copied verbatim; nothing here names a fixture, a file or a symbol of one.
 */

import python

predicate startOf(AstNode n, string file, int line, int col) {
  file = n.getLocation().getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

/** A method call `r.m(...)` (P-Hybrid-1). */
class MethodCall extends Call {
  MethodCall() { this.getFunc() instanceof Attribute }
}

/** A method call on an attribute, `a.b.m(...)` (P-Hybrid-1). */
class AttributeMethodCall extends MethodCall {
  AttributeMethodCall() { this.getFunc().(Attribute).getObject() instanceof Attribute }
}

/** `v = e` with exactly one plain name as its target. */
class Definition extends AssignStmt {
  Definition() { count(this.getATarget()) = 1 and this.getATarget() instanceof Name }

  Name getName() { result = this.getATarget() }
}

/** `e` is `root` or any expression below it. */
predicate within(Expr root, Expr e) { e = root or e.getParentNode+() = root }
