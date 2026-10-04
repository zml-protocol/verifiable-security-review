/**
 * @name secreview bridge verifier: argument_binding (Go)
 * @description A call argument and the parameter it binds to, when the call resolves statically
 *              to one function with a body (no interface dispatch, no function value) and the
 *              argument does not fall into a variadic parameter.
 * @kind table
 * @id secreview/bridge-argument-binding-go
 */

import go
import BridgeCommon

from CallArgument arg, FuncDecl callee, ParameterNode param, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  callee = arg.getCall().getTarget().getFuncDecl() and
  exists(callee.getBody()) and
  not (callee.isVariadic() and arg.getIndex() >= callee.getNumParameter() - 1) and
  param.getParameter() = callee.getParameter(arg.getIndex()) and
  startOf(arg, ff, fl, fc) and
  startOf(param, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
