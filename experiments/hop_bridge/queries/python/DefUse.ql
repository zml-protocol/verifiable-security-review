/**
 * @name secreview bridge verifier: def_use (Python)
 * @description A parameter or single-name definition and a later definition or call that reads the
 *              defined value, by local value flow into its right-hand side or one of its arguments.
 * @kind table
 * @id secreview/bridge-def-use-python
 */

import python
import semmle.python.dataflow.new.DataFlow
import BridgeCommon

/** The data-flow node holding the value that `n` defines. */
predicate defines(AstNode n, DataFlow::Node value) {
  value.(DataFlow::ParameterNode).getParameter() = n
  or
  value.asCfgNode().getNode() = n.(Definition).getName()
}

from AstNode from_, DataFlow::Node value, AstNode to, Expr read, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  defines(from_, value) and
  DataFlow::localFlow(value, DataFlow::exprNode(read)) and
  not read = from_.(Definition).getName() and
  (
    within(to.(Definition).getValue(), read)
    or
    within(to.(Call).getAnArg(), read)
    or
    within(to.(Call).getANamedArg().(Keyword).getValue(), read)
  ) and
  to != from_ and
  startOf(from_, ff, fl, fc) and
  startOf(to, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
