/**
 * @name secreview hop verifier: registry_dispatch
 * @description Method calls `r.m(...)` whose receiver may hold an instance of a class, and the
 *              method `m` that instance would run. Instances move by the standard value-flow
 *              steps plus one generic registry model: a container named by a module-level
 *              variable or a class attribute is one abstract location, and a read from it with a
 *              run-time key may return any element stored into it under a run-time key or the
 *              same literal key.
 * @kind table
 * @id secreview/hop-registry-dispatch
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.internal.DataFlowDispatch as Dispatch
import HopCommon

/** `k` defines attribute `name` in its class body. */
predicate definesClassAttribute(Class k, string name) {
  exists(AssignStmt s | s.getScope() = k and s.getATarget().(Name).getId() = name)
}

/** `e` evaluates to class `k` or to an instance of it (`self`, `cls`, or the class itself). */
predicate classOrInstance(Expr e, Class k) {
  e = Dispatch::classTracker(k).asExpr() or
  e = Dispatch::selfTracker(k).asExpr() or
  e = Dispatch::clsArgumentTracker(k).asExpr()
}

/** The abstract location of the container `e` denotes, when it has a stable name. */
string container(Expr e) {
  exists(GlobalVariable v | e.(Name).getVariable() = v |
    result = "global " + v.getScope().(Module).getFile().getRelativePath() + ":" + v.getId()
  )
  or
  exists(Attribute a, Class k, Class owner |
    a = e and
    classOrInstance(a.getObject(), k) and
    owner = Dispatch::getADirectSuperclass*(k) and
    definesClassAttribute(owner, a.getName()) and
    result = "class " + owner.getQualifiedName() + "." + a.getName()
  )
  or
  // a name bound in a class body, as the class body itself refers to it
  exists(Class k, string name |
    e.(Name).getId() = name and
    e.getScope() = k and
    definesClassAttribute(k, name) and
    result = "class " + k.getQualifiedName() + "." + name
  )
}

/** A literal string key, or "" for a key only known at run time. */
string keyOf(Expr index) {
  result = index.(StringLiteral).getText()
  or
  not index instanceof StringLiteral and result = ""
}

/** `value` is stored into container `loc` under `key`. */
predicate stores(Expr value, string loc, string key) {
  // c[k] = value
  exists(AssignStmt s, Subscript sub |
    sub = s.getATarget() and
    value = s.getValue() and
    loc = container(sub.getObject()) and
    key = keyOf(sub.getIndex())
  )
  or
  // c.append(value), c.add(value), c.insert(i, value), c.setdefault(k, value)
  exists(MethodCall c | loc = container(c.getReceiver()) |
    c.getMethodName() = ["append", "add"] and value = c.getArg(0) and key = ""
    or
    c.getMethodName() = "insert" and value = c.getArg(1) and key = ""
    or
    c.getMethodName() = "setdefault" and value = c.getArg(1) and key = keyOf(c.getArg(0))
  )
  or
  // c = {k: value, ...} / [value, ...] / (value, ...) / {value, ...}
  exists(AssignStmt s, Expr lit | lit = s.getValue() and loc = container(s.getATarget()) |
    exists(KeyValuePair p | p = lit.(Dict).getAnItem() and value = p.getValue() and key = keyOf(p.getKey()))
    or
    value = [lit.(List).getAnElt(), lit.(Tuple).getAnElt(), lit.(Set).getAnElt()] and key = ""
  )
}

/** `read` returns an element of container `loc` selected by `key`. */
predicate reads(Expr read, string loc, string key) {
  exists(Subscript sub | sub = read and not sub = any(AssignStmt s).getATarget() |
    loc = container(sub.getObject()) and key = keyOf(sub.getIndex())
  )
  or
  exists(MethodCall c | c = read and c.getMethodName() = ["get", "pop"] |
    loc = container(c.getReceiver()) and key = keyOf(c.getArg(0))
  )
}

module InstanceConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { Dispatch::resolveClassCall(n.asCfgNode(), _) }

  predicate isSink(DataFlow::Node n) { n.asExpr() = any(MethodCall c).getReceiver() }

  predicate isAdditionalFlowStep(DataFlow::Node stored, DataFlow::Node read) {
    exists(string loc, string ks, string kr |
      stores(stored.asExpr(), loc, ks) and
      reads(read.asExpr(), loc, kr) and
      (ks = "" or kr = "" or ks = kr)
    )
  }
}

module InstanceFlow = DataFlow::Global<InstanceConfig>;

from
  DataFlow::Node src, DataFlow::Node sink, Class cls, MethodCall c, Function f, string ff, int fl,
  int fc, string tf, int tsl, int tel
where
  InstanceFlow::flow(src, sink) and
  Dispatch::resolveClassCall(src.asCfgNode(), cls) and
  sink.asExpr() = c.getReceiver() and
  f = Dispatch::findFunctionAccordingToMro(cls, c.getMethodName()) and
  startOf(c, ff, fl, fc) and
  functionLines(f, tf, tsl, tel)
select ff, fl, fc, tf, tsl, tel
