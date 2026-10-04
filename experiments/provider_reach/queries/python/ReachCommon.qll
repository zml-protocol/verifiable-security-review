/**
 * Endpoint matching and the flow configuration shared by the Spike P Python queries.
 * Endpoints come from the generated Endpoints.qll; nothing here names a fixture.
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import Endpoints

/** `n` starts on `line` of `file` and, unless `name` is "*", is that variable. */
predicate at(DataFlow::Node n, string file, int line, string name) {
  n.getLocation().getFile().getRelativePath() = file and
  n.getLocation().getStartLine() = line and
  (
    name = "*"
    or
    n.(DataFlow::ParameterNode).getParameter().getName() = name
    or
    n.asExpr().(Name).getId() = name
  )
}

/** Standard library flow and taint steps only: no additional steps, barriers or models. */
module ReachConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) {
    exists(string f, int l, string v | sourceAt(f, l, v) and at(n, f, l, v))
  }

  predicate isSink(DataFlow::Node n) {
    exists(string f, int l, string v | sinkAt(f, l, v) and at(n, f, l, v))
  }
}
