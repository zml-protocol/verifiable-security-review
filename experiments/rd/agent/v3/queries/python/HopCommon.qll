/** RD v3 copy of the frozen Python endpoint helpers; endpoint roles are unchanged. */

import python

class MethodCall extends Call {
  MethodCall() { this.getFunc() instanceof Attribute }

  string getMethodName() { result = this.getFunc().(Attribute).getName() }

  Expr getReceiver() { result = this.getFunc().(Attribute).getObject() }
}

class AttributeMethodCall extends MethodCall {
  AttributeMethodCall() { this.getReceiver() instanceof Attribute }
}

predicate startOf(AstNode n, string file, int line, int col) {
  file = n.getLocation().getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

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
