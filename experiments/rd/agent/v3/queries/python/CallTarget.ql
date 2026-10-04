/**
 * @name secreview RD v3 verifier: call_typed_attribute
 * @description Nested attribute-method calls and the methods reached through standard dispatch
 *              or an instance's class-attribute value.
 * @kind table
 * @id secreview/rd-v3-call-typed-attribute-python
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.internal.DataFlowDispatch as Dispatch
import HopCommon

/** `k` assigns `value` to class attribute `name` in its class body. */
predicate classAttributeValue(Class k, string name, Expr value) {
  exists(AssignStmt s |
    s.getScope() = k and
    s.getATarget().(Name).getId() = name and
    value = s.getValue()
  )
}

/** Track the class instance used as the object of an attribute read. */
module AttributeObjectConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { Dispatch::resolveClassCall(n.asCfgNode(), _) }

  predicate isSink(DataFlow::Node n) { n.asExpr() = any(Attribute a).getObject() }
}

module AttributeObjectFlow = DataFlow::Global<AttributeObjectConfig>;

/** `read` obtains `value` from a class attribute on its receiver's concrete class or an ancestor. */
predicate readsClassAttributeValue(Attribute read, Expr value) {
  exists(DataFlow::Node src, DataFlow::Node sink, Class cls, Class owner |
    AttributeObjectFlow::flow(src, sink) and
    Dispatch::resolveClassCall(src.asCfgNode(), cls) and
    sink.asExpr() = read.getObject() and
    owner = Dispatch::getADirectSuperclass*(cls) and
    classAttributeValue(owner, read.getName(), value)
  )
}

/** Carry the assigned class-attribute value to a read from a proven receiver class. */
module NestedReceiverConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { Dispatch::resolveClassCall(n.asCfgNode(), _) }

  predicate isSink(DataFlow::Node n) { n.asExpr() = any(AttributeMethodCall c).getReceiver() }

  predicate isAdditionalFlowStep(DataFlow::Node stored, DataFlow::Node read) {
    readsClassAttributeValue(read.asExpr().(Attribute), stored.asExpr())
  }
}

module NestedReceiverFlow = DataFlow::Global<NestedReceiverConfig>;

predicate resolvedTarget(AttributeMethodCall c, Function f) {
  exists(CallNode cn | cn.getNode() = c and Dispatch::resolveCall(cn, f, _))
  or
  exists(DataFlow::Node src, DataFlow::Node sink, Class cls |
    NestedReceiverFlow::flow(src, sink) and
    Dispatch::resolveClassCall(src.asCfgNode(), cls) and
    sink.asExpr() = c.getReceiver() and
    f = Dispatch::findFunctionAccordingToMro(cls, c.getMethodName())
  )
}

from AttributeMethodCall c, Function f, string ff, int fl, int fc, string tf, int tsl, int tel
where
  resolvedTarget(c, f) and
  startOf(c, ff, fl, fc) and
  functionLines(f, tf, tsl, tel)
select ff, fl, fc, tf, tsl, tel
