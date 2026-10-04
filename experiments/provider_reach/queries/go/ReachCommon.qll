/**
 * Endpoint matching and the flow configuration shared by the Spike P Go queries.
 * Endpoints come from the generated Endpoints.qll; nothing here names a fixture.
 */

import go
import Endpoints

/** `n` starts on `line` of `file` and, unless `name` is "*", is that variable. */
predicate at(DataFlow::Node n, string file, int line, string name) {
  n.getFile().getRelativePath() = file and
  n.getStartLine() = line and
  (
    name = "*"
    or
    exists(Variable v | v.getName() = name |
      n.asExpr() = v.getAReference() or
      n = DataFlow::ssaNode(any(SsaVariable s | s.getSourceVariable() = v))
    )
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
