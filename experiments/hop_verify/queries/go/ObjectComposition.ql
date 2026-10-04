/**
 * @name secreview hop verifier: object_composition
 * @description An object (defined by a statement, or modified by a field store on its variable)
 *              and a later field store that puts it, directly or nested in literals or call
 *              arguments, into another object's field.
 * @kind table
 * @id secreview/hop-object-composition
 */

import go
import HopCommon

/** The object defined or modified at `s` is the value read at `use`. */
predicate objectReaches(AstNode s, Expr use) {
  // defined at s: local value flow from that definition
  exists(DataFlow::SsaNode src |
    src.getDefinition() = s.(Definition).getSsaDefinition() and
    DataFlow::localFlow(src, DataFlow::exprNode(use))
  )
  or
  // modified at s through `v.f = ...`: the same SSA version of v is read at use, after s
  exists(FieldStore m, SsaVariable v |
    m = s and
    v.getAUse() = IR::evalExprInstruction(m.getBase()) and
    v.getAUse() = IR::evalExprInstruction(use) and
    use.getLocation().getStartLine() > m.getLocation().getEndLine()
  )
}

from AstNode s, FieldStore store, Expr stored, Expr use, string ff, int fl, int fc, string tf, int tl, int tc
where
  stored = store.getAStoredExpr() and
  within(stored, use) and
  objectReaches(s, use) and
  s != store and
  startOf(s, ff, fl, fc) and
  startOf(store, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
