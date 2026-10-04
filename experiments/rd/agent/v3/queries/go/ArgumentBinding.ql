/**
 * @name secreview RD v3 verifier: argument_binding (Go)
 * @description Frozen static binding plus a bounded function-parameter callback binding: a
 *              function name passed directly into a statically resolved parameter may be the
 *              target of a call through that parameter. Relation truth and endpoint roles stay
 *              unchanged.
 * @kind table
 * @id secreview/rd-v3-argument-binding-go
 */

import go
import BridgeCommon

predicate possibleCallee(CallExpr call, FuncDecl callee) {
  callee = call.getTarget().getFuncDecl()
  or
  exists(Parameter callback, CallExpr binding, int callbackIndex |
    call.getCalleeExpr().stripParens() = callback.getAReference() and
    callbackIndex = callback.getIndex() and
    binding.getTarget().getFuncDecl() = callback.getFunction() and
    binding.getArgument(callbackIndex).stripParens() = callee.getFunction().getAReference()
  )
}

from CallArgument arg, FuncDecl callee, ParameterNode param, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  possibleCallee(arg.getCall(), callee) and
  exists(callee.getBody()) and
  not (callee.isVariadic() and arg.getIndex() >= callee.getNumParameter() - 1) and
  param.getParameter() = callee.getParameter(arg.getIndex()) and
  startOf(arg, ff, fl, fc) and
  startOf(param, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
