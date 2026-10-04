/**
 * @name secreview chain connector: same object (Go)
 * @description Object nodes and the SSA definition each one stands for (PREREGISTRATION.md
 *              §12.1). An object node is a statement defining exactly one local variable
 *              (v := e, v = e, var v = e) or a store into one field of a plain local variable
 *              (v.f = e). Two object nodes name the same object iff they stand for the same
 *              explicit SSA definition. No row (a phi-merged or captured definition, several
 *              variables defined at once, a variable that may be referenced indirectly) means
 *              the connector cannot prove sameness. Nothing here names a fixture.
 * @kind table
 * @id secreview/chain-same-object-go
 */

import go

predicate startOf(Locatable n, string file, int line, int col) {
  file = n.getFile().getRelativePath() and
  line = n.getLocation().getStartLine() and
  col = n.getLocation().getStartColumn()
}

/** `n` makes definition `d` of a variable, and defines no other variable. */
predicate definesOnly(AstNode n, SsaExplicitDefinition d) {
  (
    n.(SimpleAssignStmt).getNumLhs() = 1 and d.getInstruction() = IR::assignInstruction(n, 0)
    or
    n.(ValueSpec).getNumName() = 1 and d.getInstruction() = IR::initInstruction(n, 0)
  )
}

/** `n` is `v.f = e` on a plain local variable whose read is reached by definition `d`. */
predicate storesInto(AstNode n, SsaExplicitDefinition d) {
  exists(SimpleAssignStmt a, SelectorExpr sel, SsaVariable v |
    a = n and
    a.getNumLhs() = 1 and
    sel = a.getLhs() and
    sel.getSelector().refersTo(any(Field f)) and
    v.getAUse() = IR::evalExprInstruction(sel.getBase()) and
    v.getDefinition() = d
  )
}

from AstNode n, SsaExplicitDefinition d, string file, int line, int col, string kind
where
  (
    definesOnly(n, d) and kind = "definition"
    or
    storesInto(n, d) and kind = "field_store"
  ) and
  not d.getSourceVariable().mayHaveIndirectReferences() and
  startOf(n, file, line, col)
select file, line, col, kind, d.getSourceVariable().getName(),
  d.getInstruction().getLocation().getStartLine(), d.getInstruction().getLocation().getStartColumn()
