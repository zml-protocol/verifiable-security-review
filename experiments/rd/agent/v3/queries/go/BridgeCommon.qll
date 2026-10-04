/** RD v3 copy of the frozen Go bridge endpoint helpers; endpoint roles are unchanged. */

import go

predicate startOf(Locatable n, string file, int line, int col) {
  file = n.getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

class Definition extends AstNode {
  Definition() {
    this.(Assignment).getAnLhs().(Ident).refersTo(any(LocalVariable v))
    or
    this.(ValueSpec).getANameExpr().refersTo(any(LocalVariable v)) and
    exists(this.(ValueSpec).getAnInit())
  }
}

class ParameterNode extends Ident {
  Parameter p;

  ParameterNode() { this = p.getDeclaration() and not p instanceof ReceiverVariable }

  Parameter getParameter() { result = p }
}

class RangeValue extends Expr {
  RangeStmt rs;

  RangeValue() { this = rs.getValue() and this instanceof Ident }

  RangeStmt getRange() { result = rs }
}

class CallArgument extends Expr {
  CallExpr call;
  int index;

  CallArgument() { this = call.getArgument(index) }

  CallExpr getCall() { result = call }

  int getIndex() { result = index }
}

predicate defines(AstNode n, SsaExplicitDefinition d) {
  n instanceof Definition and
  exists(int i |
    d.getInstruction() = IR::assignInstruction(n, i) or
    d.getInstruction() = IR::initInstruction(n, i)
  )
  or
  d.getInstruction() = IR::initParamInstruction(n.(ParameterNode).getParameter())
  or
  d.getInstruction() = IR::assignValueInstruction(n.(RangeValue).getRange())
}

predicate within(Expr root, Expr e) { e = root or e.getParent+() = root }
