/**
 * @name secreview hop verifier: call_typed_attribute
 * @description Method calls on attributes and the functions the standard call graph resolves them to.
 * @kind table
 * @id secreview/hop-call-typed-attribute
 */

import python
import semmle.python.dataflow.new.internal.DataFlowDispatch as Dispatch
import HopCommon

from AttributeMethodCall c, CallNode cn, Function f, string ff, int fl, int fc, string tf, int tsl, int tel
where
  cn.getNode() = c and
  Dispatch::resolveCall(cn, f, _) and
  startOf(c, ff, fl, fc) and
  functionLines(f, tf, tsl, tel)
select ff, fl, fc, tf, tsl, tel
