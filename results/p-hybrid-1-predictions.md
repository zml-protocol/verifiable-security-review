# P-Hybrid-1 预测（在 cal、eval 任何运行之前写下，随第一次冻结一起提交）

依据：dev 上的结果（`p-hybrid-1-dev.json`，5 种关系在 dev 上都是 SUPPORTED，没有假跳被判为 VERIFIED），加上 Spike P 事后诊断里观察到的 CodeQL 行为。

## cal（留出的合成代码）

| 关系 | 预测 | 把握 | 主要风险 |
|---|---|---|---|
| field_flow | SUPPORTED | 90% | — |
| object_composition | SUPPORTED | 90% | — |
| guard_property | SUPPORTED | 90% | — |
| call_typed_attribute | SUPPORTED | 90% | — |
| registry_dispatch | SUPPORTED | 75% | 通过函数参数写入的全局 dict（`install`）、`.get` 读取、同名类属性 |

没有假跳被判为 VERIFIED：90%。

## eval

| 关系 | 预测 | 把握 | 主要风险 |
|---|---|---|---|
| call_typed_attribute | SUPPORTED | 85% | Spike P 的事后诊断中，taint 已经经过 `jwt.py:104` 进入 `deserialize_compact` |
| registry_dispatch | 两侧都 VERIFIED 的可能性为 50%（否则 BLIND） | 50% | `register_jws_rfc7518(cls)` 里的 `cls.register_algorithm(algorithm)`：接收者是一个持有类对象的**参数**，标准调用图未必能解析；另外，`JWS_ALGORITHMS` 列表是跨模块导入的 |
| field_flow | SUPPORTED | 85% | 需要 `strings.TrimPrefix`、`filepath.ToSlash`、`strings.ReplaceAll` 的标准 taint 模型 |
| guard_property | SUPPORTED | 80% | 需要 CodeQL 把 `goodResponseHandler` 当作 SSA 变量（没有取地址） |
| object_composition | SUPPORTED | 80% | 同上 |

- 没有假跳被判为 VERIFIED：90%。reversed 变异大多会因形状检查被判为 CONTRADICTED（object_composition 的 reversed 两端种类都合法，预计为 UNVERIFIED）。
- 6 个 wrong_revision 变异全部被引用检查拦下（这一点已经由 `check` 确定，不算预测）。
- 路由：`HYBRID_2_LIMITED_SCOPE`，85%。registry_dispatch 是否进入 Hybrid-2，取决于上面那 50%。
