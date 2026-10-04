/**
 * @name secreview endpoint resolution
 * @description Every data-flow node the endpoints resolve to; a pair with no source or
 *              no sink node is a plumbing failure, not a capability result (§9.5).
 * @kind problem
 * @problem.severity recommendation
 * @id secreview/resolve-endpoints-python
 */

import python
import ReachCommon

from DataFlow::Node n, string role
where
  ReachConfig::isSource(n) and role = "source"
  or
  ReachConfig::isSink(n) and role = "sink"
select n, role
