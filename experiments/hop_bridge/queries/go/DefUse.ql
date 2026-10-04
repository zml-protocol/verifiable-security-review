/**
 * @name secreview bridge verifier: def_use (Go)
 * @description A definition (statement, parameter or range value) and a later definition or call
 *              argument that reads the defined value, by local value flow into the right-hand
 *              side or the argument (the value is read in computing it).
 * @kind table
 * @id secreview/bridge-def-use-go
 */

import go
import BridgeCommon

from AstNode from_, SsaExplicitDefinition d, AstNode to, Expr read, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  defines(from_, d) and
  DataFlow::localFlow(DataFlow::ssaNode(d), DataFlow::exprNode(read)) and
  (
    within(to.(Definition).(Assignment).getAnRhs(), read)
    or
    within(to.(Definition).(ValueSpec).getAnInit(), read)
    or
    within(to.(CallArgument), read)
  ) and
  to != from_ and
  startOf(from_, ff, fl, fc) and
  startOf(to, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
