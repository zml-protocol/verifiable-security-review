/**
 * @name secreview bridge verifier: range_element (Go)
 * @description A definition (statement or parameter) of a collection and the value variable of a
 *              range over that same value (local value flow into the ranged expression).
 * @kind table
 * @id secreview/bridge-range-element-go
 */

import go
import BridgeCommon

from AstNode from_, SsaExplicitDefinition d, RangeValue value, string ff, int fl, int fc,
  string tf, int tl, int tc
where
  defines(from_, d) and
  not from_ instanceof RangeValue and
  DataFlow::localFlow(DataFlow::ssaNode(d), DataFlow::exprNode(value.getRange().getDomain())) and
  startOf(from_, ff, fl, fc) and
  startOf(value, tf, tl, tc)
select ff, fl, fc, tf, tl, tc
