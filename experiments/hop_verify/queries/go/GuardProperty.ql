/**
 * @name secreview hop verifier: guard_property
 * @description A keyed field inside the literal that defines a local variable, and a field store
 *              into that same variable (same SSA version): the field is a property of the object
 *              the store writes into.
 * @kind table
 * @id secreview/hop-guard-property
 */

import go
import HopCommon

from
  Definition d, Expr literal, KeyedField property, FieldStore store, SsaVariable v, string ff,
  int fl, int fc, string tf, int tl, int tc
where
  v.getDefinition() = d.getSsaDefinition() and
  d.getSsaDefinition().getRhs() = IR::evalExprInstruction(literal) and
  literalPart(literal, property) and
  v.getAUse() = IR::evalExprInstruction(store.getBase()) and
  startOf(property, ff, fl, fc) and
  startOf(store, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
