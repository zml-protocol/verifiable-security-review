# Spike P：校准 pilot 的结果说明

- 使用 CodeQL `codeql-bundle-v2.27.1`（sha256 `1d380f79…c6b815`）。查询是第一次冻结（`7702441`）时的版本，**未做任何修改**。
- pilot 只使用非评估代码（`pilot.yaml`），评估 fixture 在此阶段完全没有运行。
- **流程检查全部通过**：7 组的端点都解析到了节点；plumbing 组（`pilot-py-direct`、`pilot-go-call`）都找到了经过预期行的路径。因此**没有做任何流程修复**。Trailmark 的 pilot 也全部通过。

## 校准结果（`spike-p-calibration.json`）：在冻结查询下的表达能力

| 关系 | 事先预测 | 结果 |
|---|---|---|
| call_typed_attribute | true | **true** |
| registry_dispatch | false | **false** |
| field_flow | true | **false**（预测落空） |
| object_composition | true | **false**（预测落空） |

## 诊断（说明性质，不参与评分，也不改变任何分类）

为了确认 false 是能力上的结果而不是流程故障，另写了一个临时查询，只在 pilot 的数据库上运行，查看污点能传到哪里。这个查询没有放进仓库，冻结的查询也没有改动。

- **Go 的 field_flow**：`names` → `n` → `path` → `TrimPrefix` → `ReplaceAll`，一直传到结构体字面量里的 `name`（第 30 行），但**没有从这个字段传到包含它的结构体、切片和返回值**。
- **Go 的 object_composition**：从 `extra` 传到对 `good.Routes` 的字段写入，但**没有传到包含它的 `good` 和 `p.HandleResponse`**。
- 两者的原因相同：默认的 Go 污点模型不会因为字段内容被污染，就把包含它的结构体（容器）也当作被污染；而 sink 是整个结构体。要继续传播，需要在查询配置里允许隐式读取（`allowImplicitRead`）之类的设置，这是冻结规则不允许的。
- **Python 的 registry_dispatch**：污点传到了第 30 行 `chosen.check(label, proof)` 的实参，但**没有进入 `Relaxed.check`**。从字典里取出的实例上的方法调用，没有被解析成派发，而且 `TABLE[label]` 的结果也没有因为键被污染而被污染。预测的结论（false）是对的，但我事先给的理由（「选择」那一步不在路径上）只说对了一半：实际上派发本身就没有被解析。

## 这些结果意味着什么

在冻结查询下，5 种关系里只有 call_typed_attribute 可以表达。guard_property 事先就判定为 false，另外三种由校准判定为 false。因此评估阶段的 CodeQL 预计只会在 Authlib 的 `jwt.py:104` 上接受实际检验。这只说明**这个基线查询在操作层面的边界**，不代表 CodeQL 这门语言在理论上做不到（PREREGISTRATION.md §9.3）。
