# 链复现报告（§12）：局部可核验证据链的可行性

- 冻结 `671fa12` → 连接器留出校准 `097bd43`（安全：没有不安全的对，「同一」对 9/9 得到证明）→ 评估 fixture 的连接器输出 `fa3119a`（只在校准门槛通过之后生成）→ 30 个新会话 → 分数 `028f6ed`（在查看任何细节之前提交）。
- 30 个会话在第一次尝试中全部 `VALID:completed`。harness 不变量全部为 0：没有上下文泄露、没有外部工具、没有 harness 错误、scorer 没有拒绝任何锁定的跳，冻结的核验器与连接器输出的 hash 一致。
- 名义花费 $12.05。没有反馈，没有 A/B，没有重评分任何旧实验。

## 结果（状态：`REPORTED`；描述性，没有成功门槛）

| fixture | FULL_CHAIN 的 block（两个 revision 都完整） | 95% Wilson 区间 | 各 revision 的分类（每个 fixture 共 20 个） |
|---|---|---|---|
| Authlib | **10/10** | 72–100% | FULL 20 |
| Caddy | **3/10** | 11–60% | FULL 6，**QUALIFIER_GAP 12**，INTERNAL_GAP 1，NO_EVIDENCE 1 |
| File Browser | **5/10** | 24–76% | FULL 10，**ENTRY_GAP 10**（最长后半段都是 1 条边） |
| 合计 | **18/30** | 42–75% | |

这里的「完整」是 **fully VERIFIED chain**，即被冻结核验器接受的链，不是 ground-truth 意义上的正确链。三个 fixture 也不是安全代码总体的随机样本。

## 事后诊断（在分数提交之后进行，不改变结果）

1. **Caddy 的 12 个 QUALIFIER_GAP 全部是没有提出 guard 跳。**
   - r0–r5 的初稿里一个 guard 跳都没有，但从 entry 到 terminal 的已核验路径在这 12 个 revision 中全部存在。
   - r6–r8 提出了 guard 跳（锚在 `Match:` 或 `StatusCode:`），都被核验、挂上了路径，结果为 FULL。
   - r9 的 guard 指向了 `rpHandler` 的写入（错误的目标），被正确地判为 UNVERIFIED；它的主路径也不完整。
   - 也就是说，缺的是本案最关键的安全条件（只在 2xx 时执行），而不是路径。
2. **File Browser 的 10 个 ENTRY_GAP 来自 5 个 run 的同一种选择。** 这 5 个 run 在两个 revision 上都把 field_flow 的起点放在翻转行（base 的 `ToSlash`、head 的 `ReplaceAll` 对 `nameInArchive` 的重新赋值），另外 5 个 run 都从 125 的 `TrimPrefix` 定义出发，结果为 FULL。
   - 从 125 直接到 `NameInArchive` 的一跳，本身就能用 field_flow 表达并被核验。所以这个缺口是 **agent 可以自己补上的**，不只是核验器的盲区。
3. **同一对象连接器不是装饰。** 在 Caddy 的 18 个路径连通的 revision 中，有 6 个（r2、r7、r8）的连通依赖于被证明的同一对象。
   - 作为诊断输出（不是正式计分模式），如果只用 C1，r7、r8 会从 FULL 变成 ENTRY_GAP，Caddy 的 FULL 会从 3/10 降到 1/10。
   - 连接器在留出校准中是安全的（0 个不安全），所以这些连通是有保守依据的。
4. **与设计诊断的差别。** 设计诊断（P-Hybrid-2 的 15 个初稿，文本启发式 C2）是 13/15，本次正式复现是 18/30。
   - Caddy 漏掉 guard 的比例是 6/10（设计诊断中是 0/5）；File Browser 从翻转行出发的比例是 5/10（设计诊断中是 2/5）。
   - 两者是不同的会话样本，设计诊断只是设计信息。这个差距本身说明：同一个 prompt，会话之间在「是否提出关键限定条件」「从哪里起链」上的变化很大。
5. 次要统计：共 158 个跳，其中 `unsupported` 44 个（28%），不匹配 golden 的 novel 跳 94 个（59%）；按预注册，这些不做盲审。

## 结论的边界

- 这只说明，在**当前可表达的局部证据子图**内，agent 加核验器加连接器，一次性就能组成完整的已核验链：Authlib 稳定做到，Caddy 和 File Browser 大约各一半或更少。
- 它**不说明**系统已经能从真实入口端到端证明漏洞路径（Spike P 的端点不可表达，见 §12.0）。
- 真实入口需要独立的 P-extension：Go 跨函数调用、参数绑定、定义 → 重新定义，以及配置 → 运行时。

## 对下一步的含义（供用户和 Codex 讨论）

- **暂缓的完整性反馈 A/B（原 B）现在有了实验空间。** 当初暂缓，是因为设计诊断只有 2/15 个不完整、而且原因单一。本次正式复现中有 12/30 个 block 不完整，原因有两种（Caddy 漏掉 guard、File Browser 的起点选择），**两种都可以由 agent 自己补上**。
- 但要让一位的完整性反馈能够被 agent 用上，任务里必须写明「要求的 entry 和 behavior」，这本身就是提示。而且 QUALIFIER_GAP 属于「路径存在、但缺必要条件」，反馈的定义里必须把「必要条件」包括进去。这些需要重新设计并预注册，不能从本次结果直接接上去。
