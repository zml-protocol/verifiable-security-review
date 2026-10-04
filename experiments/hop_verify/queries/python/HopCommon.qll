/**
 * Node kinds shared by the P-Hybrid-1 Python hop verifiers (PREREGISTRATION.md §10).
 * Nothing here names a fixture, a file or a symbol of one.
 */

import python

/** A method call `r.m(...)`. */
class MethodCall extends Call {
  MethodCall() { this.getFunc() instanceof Attribute }

  string getMethodName() { result = this.getFunc().(Attribute).getName() }

  Expr getReceiver() { result = this.getFunc().(Attribute).getObject() }
}

/** A method call on an attribute, `a.b.m(...)`. */
class AttributeMethodCall extends MethodCall {
  AttributeMethodCall() { this.getReceiver() instanceof Attribute }
}

/** The start of `n`, as the hop matcher expects it: file, line, column (1-based). */
predicate startOf(AstNode n, string file, int line, int col) {
  file = n.getLocation().getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

/** `f` occupies lines `sl`..`el` of `file`: from its `def` to its last nested node. */
predicate functionLines(Function f, string file, int sl, int el) {
  file = f.getLocation().getFile().getRelativePath() and
  sl = f.getLocation().getStartLine() and
  el =
    max(int l |
      exists(Stmt s | s.getScope().getEnclosingScope*() = f | l = s.getLocation().getEndLine())
      or
      exists(Expr e | e.getScope().getEnclosingScope*() = f | l = e.getLocation().getEndLine())
    )
}
