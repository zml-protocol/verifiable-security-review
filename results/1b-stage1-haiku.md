# Spike 1B 阶段 1：Haiku 热身报告

- 协议：v1（预注册 `f623da3`），分数冻结于 `519efba`（`1b-stage1-haiku.json`，在查看任何 transcript 之前提交）
- 模型：`claude-haiku-4-5-20251001`（API 实际返回的模型一致），Claude Code 2.1.280
- 规模：80 个 slot，全部 `VALID`，结果均为 `completed`，没有重跑；花费 $5.12

## 判定：通过，进入阶段 2

### harness 不变量（§2.1）

| 不变量 | 要求 | 结果 |
|---|---|---|
| anchor 审计失败 | 0 | 0 |
| 被接受的跨 revision 引用 | 0 | 0 |
| 工具层内部错误 | 0 | 0 |
| 调用了 secreview 以外的工具 | 0 | 0 |
| 重新评分出现差异 | 0 | 0（唯一的差异是 provenance 里的 `harness_commit`，这是冻结分数的那次提交本身带来的） |
| INFRA_INVALID 占比 | ≤ 5% | 0% |

### 协议合理性门槛（§2.2）

| 指标 | 门槛 | 结果 |
|---|---|---|
| 归因正确率（全部条件） | ≥ 90% | 100% |
| 证据完整且归因正确率 | ≥ 80% | 87.5% |
| swap 镜像一致性 | ≥ 90% | 100% |
| identity 不一致率（run 级） | ≤ 5% | 0% |
| 负对照假 SUPPORTED 率 | ≤ 10% | 0% |

另外：重复一致性 100%；尝试阶段的引用错误率 6.7%；有 1 个 run 尝试过跨 revision 引用，被拒绝后自己改正了。

## 人工分析（§4）

### 1. 事实没有全部覆盖（10 个 run，归因全部正确）

10 个 run 都卡在同一类**合取事实**上：H1 和 H4 在 head 上都要求同时引用两处，一是 handler 里委托给 service 的那一行，二是 service 方法本身。agent 每次都只引用了 service 方法（H4 是 `get_for` 里的 owner 检查，H1 是 `delete` 本身），没有引用 handler → service 这一跳。

| 格子 | 未覆盖 |
|---|---|
| H4 / forward | 4/5 |
| H4 / identity_head | 5/5 |
| H1 / identity_head | 1/5 |

**golden 不修订。** 只引用 service 方法，证明不了入口真的走到了这段代码，不属于 §3.4 所说的「同样充分的证据」。这是一个真实信号：**agent 会引用控制点，但会漏掉连接入口和控制点的调用边。** 阶段 2 的 Caddy 和 File Browser 都依赖路径证据，证据完整率可能因此偏低。这一点记为风险；按预注册，v1 内不改协议。

### 2. 组件判断偏差（2 个 run，不影响归因）

H4 forward r3 和 H4 identity_base r0 把 `effect`（"The response returns the note's content."）在两侧都判成了 contradicted。agent 是站在攻击者的角度去评估这个组件的：非 owner 拿不到别人的 note。两侧判断一致，所以没有造成 identity 不一致，也没有影响归因。

原因在 hypothesis 的措辞：组件没有写成可以独立判断的形式。**编写 S1–S3 时要注意：** 每个组件都要能单独判断，并且写明它的前提。例如写「请求到达 handler 之后，响应会包含 note 的内容」，而不要写「攻击者能拿到 note」。

### 3. identity 措辞筛查

40 个 identity run 中有 16 个被筛查标出，**全部是误报**：命中的都是 "removes the note from storage"，描述的是删除操作本身的语义，与代码改动无关。在全部 221 条 identity 观察里，除 "remov*" 之外的改动类措辞出现了 0 次。一条盲区还明确写了 "Both base and head revisions contain identical code"。

按 §4 的四个类别（编造代码差异 / 编造语义差异 / 引用了错误 revision 的证据 / 没有依据的因果措辞）归类，**都是 0**。

这个筛查用的正则在「删除」类的 fixture 上噪声很大。v2 需要收紧；v1 内不改 scorer。

## 对阶段 2 的影响

1. 写 golden 时，合取事实要按「每一跳都要有引用」来写。阶段 1 的结果已经预示，Sonnet 5 在这一项上也可能失分。
2. 每个组件都要能独立判断，并写明前提。
3. 阶段 1 使用的是自己编写、难度偏低的 fixture。门槛全部通过只能说明 harness 和协议本身可用，不代表模型在真实代码上的能力。
