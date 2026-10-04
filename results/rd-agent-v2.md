# RD agent v2 正式实验报告

## 结论

RD v2 完成了 6 个预注册正式会话（5 个真实修复、1 个负对照）。冻结评分状态为
`REPORTED`，`harness_ok=true`；因此这是有效的模型测量，不是基础设施结果。

当前干预还不能产出可靠的端到端 verified reasoning：A 阶段的 entry / behavior 精确率与召回率分别为
3/5（60%）和 2/5（40%），B 阶段完整链为 0/5，C 阶段真实修复归因正确 3/5（60%）。负对照的两个
revision 都没有被误判为 `SUPPORTED`（0/2）。

这个结果支持继续保留 A → B → C 的分层测量框架和 fail-closed 质量门，但不支持把当前 agent/provider
组合称为“能够验证完整推理链”。下一轮应作为新的冻结版本运行，不能通过事后放宽 v2 评分来修饰结果。

## 冻结与运行来源

| 项目 | 值 |
|---|---|
| 协议 | `rd-v2` |
| 基础提交 | `52354cec7da0f8caf0424a78c5c00983e4ffbf6b` |
| 冻结提交 | `35d4a993cd30c9066a958dc42ccc95dd34c3b782` |
| 冻结 tree | `a6d091e4b4a57fca3ae450f1b8910c909c8e33e3` |
| `freeze.json` SHA-256 | `2f8e403d28543b583eef16f5a8d773ac222d3a003459b5cd947906d49a234f7f` |
| 模型 | `claude-sonnet-5`，effort `high` |
| Claude Code | `2.1.280` |
| 每会话预算 | A / B / C 为 `$3 / $3 / $1`；累计上限 `$7` |
| 全部正式会话启动上限 | `$42` |
| 实际会话成本 | `$8.763368` |
| phase 运行时长 | `2901.6s`（48m21.6s，不含配额重置的外部等待） |
| 冻结结果 | `results/rd-agent-v2.json`，提交 `331e47b` |
| 结果 SHA-256 | `b95be96903340a258eb83d5fd9209543893845754ee25aab07e00afd6fa82e80` |

结果 JSON 在打开 measured transcript 之前已经提交；本报告是提交之后的解盲定性审计。RD v1 的网络沙箱
失效记录保留在 `results/rd-agent-v1.json` 和提交 `6241243`，没有进入模型指标。

## 冻结指标

| 指标 | 结果 | Wilson 95% CI |
|---|---:|---:|
| A entry recall / precision | 3/5 = 60% | [23.07%, 88.24%] |
| A behavior recall / precision | 2/5 = 40% | [11.76%, 76.93%] |
| A qualifier recall | 0/0，不适用 | — |
| A qualifier precision | 0/1 = 0% | [0%, 79.35%] |
| B full chain | 0/5 = 0% | [0%, 43.45%] |
| B correct verified implementation | 0/5 = 0% | [0%, 43.45%] |
| B correct verified，reference-realizable 子集 | 0/4 = 0% | [0%, 48.99%] |
| C 真实修复归因正确率 | 3/5 = 60% | [23.07%, 88.24%] |
| 负对照 false-supported rate | 0/2 = 0% | [0%, 65.76%] |

负对照没有缺失结论；冻结的 unsupported-proposal burden 为 0。失败类别为：
`A_CORRECT_PROVIDER_BLIND` 1 项、`A_WRONG_B_UNREALIZABLE` 1 项、`A_WRONG_C_CORRECT` 3 项。

## 逐任务结果

| 顺序 | 任务 | A | B | C | 解盲诊断 |
|---:|---|---|---|---|---|
| 1 | task-03 · DHCP · CWE-400 | entry、behavior 均正确 | `INTERNAL_GAP`；5 条已验证边；reference 为 `PROVIDER_BLIND` | 错：两版均 `NOT_SUPPORTED` | agent 找到了真实长度 guard，但把 panic/DoS 判为 CWE-20/129/248，而不是冻结 claim 的 CWE-400；错误来自严格的 CWE 语义判断，不是没有发现改动。 |
| 2 | task-04 · LiteLLM · CWE-918 | entry 正确，behavior 错 | A 为 `NO_EVIDENCE`，B 为 `NOT_APPLICABLE`；reference 为 `REFERENCE_UNREALIZABLE` | 对：`FIX_IMPLICATED` | agent 找到了 `banned_params` 中加入 `user_config` 的改动，却把脆弱版写成 absent/context；真值要求同一 statement 两版都 present、内容发生变化。冻结 behavior 又位于 entry 之前，正向 entry → behavior 参考链本身不可实现。 |
| 3 | task-02 · Vikunja · CWE-862 | entry、behavior 均错 | 没有锁定 B artifact | 未运行 | entry 被选成 `TaskID` struct 字段，而不是真值中的 `ReadOne` 请求入口；behavior 被选成整段 query，而不是新增的 `task_id` 约束。B 已有可用工具交互后遇到会话配额提示，按冻结规则属于有效模型行为，不能重试。 |
| 4 | task-06 · DHCP 负对照 · CWE-352 | 不计分 | A 为 `INTERNAL_GAP`，B 为 `NOT_APPLICABLE`；11 条已验证边 | 对：两版均 `NOT_SUPPORTED` | agent 正确指出代码中没有 web/session/ambient-auth/state-changing 等 CSRF 要素，没有产生 false support。 |
| 5 | task-05 · Mnemosyne · CWE-347 | entry 正确，behavior 错；多报 1 个 qualifier | A 为 `NOT_APPLICABLE`，B 为 `ENTRY_GAP`；5 条已验证边 | 对：`FIX_IMPLICATED` | agent 选了 `compare_digest` 的计算，而真值是拒绝无效签名的 `if not valid_signature` guard；又把场景域中的 JWT secret 配置误报成 qualifier。 |
| 6 | task-01 · SiYuan · CWE-200 | behavior 正确，entry 错 | A 为 `INTERNAL_GAP`，B 为 `NOT_APPLICABLE`；11 条已验证边 | 对：`FIX_IMPLICATED` | agent 把更上游的请求字段 `dom` 当作 entry；真值是 claim-specific 的本地路径首次提取 `localPath := n.TokensStr()`。 |

## 失败结构

### A：主要是锚点粒度和 revision 状态表达

四类错误都不是“完全没有找到相关代码”：SiYuan 选得过于上游；Vikunja 用字段声明和整段 query 代替了
请求入口与精确授权约束；LiteLLM 找到正确改动却错误编码脆弱版状态；Mnemosyne 选择签名比较计算而不是决定
接受/拒绝的 guard，并额外发明了限定条件。这说明 A 的主要短板是把语义发现转换为冻结 schema 所要求的
statement-level anchor，而不只是代码搜索能力。

### B：0/5 由多种原因组成

- DHCP 真实任务在 A 完全正确时仍缺最后的 scalar-to-guard 关系，直接暴露 provider 盲区。
- LiteLLM 的冻结 entry 位于 behavior 之后，按正向链定义是 reference-unrealizable；这不是增加搜索次数可以修复的。
- SiYuan 与 Mnemosyne 同时受到 A 锚点错误和关系词表缺口影响，包括 callback binding、普通方法调用、
  lexical control dependency 等。
- Vikunja 在 B 已产生可用交互后达到会话配额，没有提交 artifact；协议正确地没有把它伪装成基础设施重试。

因此 0/5 不能被归结成一个单一失败点，但也不能据此授予部分成功：预注册主指标要求完整 verified chain。

### C：部分正确，但不能替代 verified chain

C 在 LiteLLM、Mnemosyne、SiYuan 上正确，在 DHCP 真实 claim 上错误，Vikunja 因 B 未锁定而没有运行。三个
`A_WRONG_C_CORRECT` 表明模型有时能在 A/B 未满足主标准时给出正确修复归因；这只是观察到的相关性，不是
可验证推理。DHCP 的错误尤其说明，claim 中 CWE 标签的严格解释可以压过对实际 guard 改动的识别。

负对照表现良好，但只有一个任务、两个 revision，区间很宽，不能据此声称已解决假阳性问题。

## 基础设施与质量门

v1 暴露了正式会话可能在网络受限环境中启动、继而把零交互 API 失败混进结果的问题。v2 在创建 measured
attempt 之前增加了认证、Anthropic endpoint 和动态 stdio MCP 精确工具面的三道检查；正式运行中这些检查
均通过。

task-06 的第一次启动在任何计费和可用交互前遇到服务配额，按协议记为 `INFRA_INVALID`；配额重置后使用
attempt-2 完成。与之相反，task-02 是在已有可用 B 交互之后遇到配额，按预注册规则保持 `VALID` 且不重试。
这种区分使运行不因结果好坏而选择性重启。

## 局限

- 只有 5 个真实修复和 1 个负对照，所有比例的置信区间都很宽。
- 真实任务的预期归因全部是 `FIX_IMPLICATED`，C 的方向类别不平衡。
- 只测试了一个模型、一个会话设置和一组冻结任务。
- LiteLLM 的正向参考链不可实现；其余 4 个真实 reference 均含 provider blind，B 的能力与 provider 覆盖无法完全分离。
- Vikunja 的 B 被会话配额截断，虽然按协议是有效观测，但减少了可解释的完整 artifact。

## 下一版建议（事后提出，不属于 v2）

1. 用新的合成、非评测样本校准 A：加入“同一 changed statement 两版均 present”和“首个 claim-specific
   extraction / decision point”的反例反馈，再冻结 v3。
2. 扩展或明确 B 的关系支持：scalar 值进入 guard、lexical control dependency、普通同对象调用、callback
   binding；先在非评测代码上验证，不能回改 v2。
3. 让 B 在预算或配额结束前自动保存 partial graph / checkpoint，避免已经完成的证据因未调用最终 submit 而消失。
4. 重新设计 entry → behavior 的方向约束，或在冻结前自动拒绝 reference-unrealizable 任务；LiteLLM 证明当前
   admissibility 检查还不够。
5. 明确 C 究竟裁决“精确 CWE 标签”还是“安全效果与修复归因”。v2 按精确冻结 claim 计分是正确的；任何
   改法都必须成为新版本。

主线决策应是：保留实验框架和质量门，判定当前 agent 干预未达到 verified reasoning 标准；如继续，先做
v3 的非评测校准与协议冻结，再运行新的正式样本。
