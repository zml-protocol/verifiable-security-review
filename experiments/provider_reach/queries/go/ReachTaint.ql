/**
 * @name secreview directed reachability (taint path)
 * @description Taint paths from the preregistered source endpoint to the sink endpoint.
 * @kind path-problem
 * @problem.severity warning
 * @id secreview/reach-taint-go
 */

import go
import ReachCommon

module Reach = TaintTracking::Global<ReachConfig>;

import Reach::PathGraph

from Reach::PathNode source, Reach::PathNode sink
where Reach::flowPath(source, sink)
select sink.getNode(), source, sink, "reaches"
