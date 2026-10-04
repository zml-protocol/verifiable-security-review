# RD 核验器一致性检查（§15.1 第 3 条；§15.10 第 2 步的最后一关）

- 冻结 `977b591` → 第 1 次尝试（没有工具故障，所以没有重跑）→ 分数 `0f7e0b1`（在查看细节之前提交）。
- 用冻结的核验器，判定全部 48 个合成关系用例；没有修改任何查询。

## Gate：`READY`

| 核验器 | provider 状态 | 真 → VERIFIED | 假 → VERIFIED | 盲区（真 → UNVERIFIED） |
|---|---|---|---|---|
| `codeql/go/argument_binding` | PARTIAL | 2/4 | 0/4 | 接口分派、函数值（AB-1：只跟随静态解析，事先已写明） |
| `codeql/go/def_use` | SUPPORTED | 4/4 | 0/2 | — |
| `codeql/go/field_flow` | SUPPORTED | 2/2 | 0/2 | — |
| `codeql/go/guard_property` | SUPPORTED | 2/2 | 0/1 | — |
| `codeql/go/object_composition` | PARTIAL | 3/4 | 0/5 | 指针别名（OC-7：核验器只跟踪同一个变量） |
| `codeql/go/range_element` | SUPPORTED | 3/3 | 0/2 | — |
| `codeql/python/call_typed_attribute` | SUPPORTED | 1/1 | 0/1 | — |
| `codeql/python/def_use` | SUPPORTED | 4/4 | 0/4 | — |
| `codeql/python/registry_dispatch` | SUPPORTED | 2/2 | 0/1 | — |

- **没有任何核验器与定义冲突**（NON_CONFORMANT 为 0）。
- 25 个假用例全部没有被判为 VERIFIED，其中包括：
  - 经由容器的两步组合（OC-3，R016 的边界）；
  - 被覆盖的旧版本（OC-4）；
  - 容器本身（OC-6）；
  - 闭包（DU-3、FF-3）；
  - 变长尾部（AB-2）；
  - 字段而非值本身（RE-3）。
- 2 个 CONTRADICTED 都是**假**用例，被形状检查正确拒绝：单变量 range 的索引（RE-1），以及方法的接收者（AB-3）。
- **局限**：合成边界用例的覆盖有限，每侧只有 1–5 个用例。这是语义一致性的关口，不是统计意义上的泛化估计。

## 冻结的两张表（`results/rd-vocabulary.json`）

- **真值词表**：
  - 9 个关系组（Go 6 个，Python 3 个），以及 entry、behavior、guard、config、dispatch_target：可采；
  - transform：退出词表。
- **provider 支持**：7 个核验器 SUPPORTED，2 个 PARTIAL（盲区如上）；没有 UNSUPPORTED，也没有 NON_CONFORMANT。
- **B 阶段规则**（`b_phase` 字段）：
  - SUPPORTED / PARTIAL 的组合可以机器核验；
  - 盲区内的真跳只会是 UNVERIFIED，例如接口分派或函数值上的实参绑定、指针别名上的组合；
  - agent 只知道某个组合能否核验，不知道具体盲区。

## 下一步

真值基础设施到此结束。下一步是 §15.10 第 3 步，按冻结的规则选择 fixture：
- 打开 OSV 快照的唯一函数，内部先调用 `conformance.gate_ready()`；
- 依次做机械筛选、固定种子排序、事先列明的人工可采条件，并记录拒绝日志；
- 冻结有序的可采队列（每种语言 4 个主用 + 2 个预留）。
