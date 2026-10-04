/**
 * @name secreview hop verifier: field_flow
 * @description A definition of a local variable and a struct field its value reaches by local
 *              taint (standard steps only): a keyed literal field or a field store.
 * @kind table
 * @id secreview/hop-field-flow
 */

import go
import HopCommon

from
  Definition d, DataFlow::SsaNode src, Expr value, AstNode target, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  src.getDefinition() = d.getSsaDefinition() and
  (
    value = target.(KeyedField).getValue()
    or
    value = target.(FieldStore).getRhs()
  ) and
  TaintTracking::localTaint(src, DataFlow::exprNode(value)) and
  startOf(d, ff, fl, fc) and
  startOf(target, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
