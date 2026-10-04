/**
 * Node kinds and SSA definitions shared by the §14 Go bridge verifiers. `Definition` is the
 * P-Hybrid-1 kind, copied verbatim; nothing here names a fixture, a file or a symbol of one.
 */

import go

predicate startOf(Locatable n, string file, int line, int col) {
  file = n.getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

/** A statement that defines local variables: `v := e`, `v = e`, `var v = e` (P-Hybrid-1). */
class Definition extends AstNode {
  Definition() {
    this.(Assignment).getAnLhs().(Ident).refersTo(any(LocalVariable v))
    or
    this.(ValueSpec).getANameExpr().refersTo(any(LocalVariable v)) and
    exists(this.(ValueSpec).getAnInit())
  }
}

/** The declaring identifier of a function parameter (receivers excluded). */
class ParameterNode extends Ident {
  Parameter p;

  ParameterNode() { this = p.getDeclaration() and not p instanceof ReceiverVariable }

  Parameter getParameter() { result = p }
}

/** The value variable of `for k, v := range x` (or `for v := range ch` over a channel). */
class RangeValue extends Expr {
  RangeStmt rs;

  RangeValue() { this = rs.getValue() and this instanceof Ident }

  RangeStmt getRange() { result = rs }
}

/** One argument of a call (the receiver of a method call is not an argument). */
class CallArgument extends Expr {
  CallExpr call;
  int index;

  CallArgument() { this = call.getArgument(index) }

  CallExpr getCall() { result = call }

  int getIndex() { result = index }
}

/** The explicit SSA definition(s) the node `n` makes. */
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

/** `e` is `root` or any expression below it. */
predicate within(Expr root, Expr e) { e = root or e.getParent+() = root }
