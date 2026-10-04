# Spike 1B 阶段 1 复验（protocol v1.1）报告

- 协议：v1.1（冻结 commit `0a96a96`）。分数冻结在 `63913d1`（`1b-stage1-haiku-v1.1.json`），冻结时还没有查看任何 transcript。
- 模型：`claude-haiku-4-5-20251001`；Claude Code 2.1.280；`apiKeySource: none`（订阅登录）。
- 规模：80 个 slot，全部 `VALID completed`，没有重跑。花费 $5.56（按 API 标价折算）。
- 按 §2.4，**阶段 1 是否通过只看这 80 次**。v1 的结果（`1b-stage1-haiku.*`）受上下文泄露影响，只保留作敏感性对照。

## 判定：通过，进入阶段 2

### harness 不变量（§2.1）

| 不变量 | 结果 |
|---|---|
| anchor 审计失败 / 被接受的跨 revision 引用 / 工具层内部错误 / 越权工具 | 0 / 0 / 0 / 0 |
| 上下文泄露（`runs_with_context_leak`） | 0。另外人工检查了第一个 run：cwd 是 `/tmp/agent-mqamvp1_`，不在 git 仓库内，memory 为空，可用工具只有 secreview 的 11 个 |
| 重新评分是否有差异 | 无（只有 `scored_at` 和 `harness_commit` 不同） |
| INFRA_INVALID 占比 | 0% |

### 协议合理性门槛（§2.2），附 v1 对照

| 指标 | 门槛 | v1.1 | v1（泄露，仅作对照） |
|---|---|---|---|
| 归因正确率 | ≥ 90% | 98.8% | 100% |
| 证据完整且归因正确率 | ≥ 80% | 92.5% | 87.5% |
| swap 镜像一致性 | ≥ 90% | 100% | 100% |
| identity 不一致率（run 级） | ≤ 5% | 2.5%（1/40） | 0% |
| 负对照假 SUPPORTED 率 | ≤ 10% | 0% | 0% |

**敏感性分析**：去掉泄露后，各项指标的变化都只有一两个 run 的量级（归因 −1 个 run，证据完整率 +4 个 run），两个方向都有。没有证据表明条件名泄露明显抬高了 v1 的成绩。但样本很小，也不能据此断言完全没有影响。

## 人工分析（§4）

1. **唯一的归因错误出现在 H3/identity_head/r0，原因是 agent 没有记录 head 一侧的观察。** 它两侧的代码都读过，在 `finish` 的摘要里也写了「base 和 head 都允许读取所有邮箱」，但只提交了 base 一侧的观察。于是 head 的状态是 NO_EVIDENCE，推导结果为 UNDETERMINED。这是**没有按协议记录**造成的失败，不是推理错误。它同时违反了「不要在 finish 里给结论」这条规则。阶段 2 的 identity 条件同样可能出现这类失败。
2. **组件判断偏差（2 个 run，归因不受影响）**：H2 forward r0 和 H2 swapped r1 把 `effect` 判成了 contradicted。原因和 v1 一样：agent 站在攻击者的角度去评估组件。阶段 2 的组件已经写成可以独立判断的形式，并写明了前提。
3. **事实未全部覆盖（5 个 run，全部集中在 H4）**：和 v1 同一个模式，只引用了 service 里的 owner 检查，没有引用 handler 委托给 service 的那一跳。阶段 2 的 golden 在每一侧都要求路径事实，所以**证据完整率很可能是阶段 2 最主要的失分来源**。
4. **identity 措辞筛查**：标出了 13 个 run，全部是 "removes the note from storage" 这类误报。除 "remov*" 之外的改动类措辞一次都没有出现。按 §4 的四个类别归类，都是 0。

## 下一步

按 §3.6 执行阶段 2 的 gate：5 个 slot，`--jobs 1`，顺序固定。执行完成后，只读取计费信息推算预算。
