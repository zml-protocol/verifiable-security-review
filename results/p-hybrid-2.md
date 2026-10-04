# P-Hybrid-2 最终报告：带类型的跳与一次性核验反馈（§11）

- 冻结 `3693529` → 15 个 block（45 个 Sonnet 5 会话）→ 分数冻结 `f873769` → 盲审表 `3855e10`。
- 盲审标签 `d848487`，改为 primary `48755f7`，日期加引号 `e47cbe3` → 最终分数 `360d374`（在查看细节之前提交）。
- 45 个会话在第一次尝试中全部 `VALID:completed`，没有任何重跑。harness 不变量全部为 0：
  - 隔离：父会话文件前后不变，快照 hash 一致，每个分支都是新会话；
  - 没有上下文泄露，没有外部工具，没有 harness 错误；
  - scorer 没有拒绝任何锁定的跳；
  - 冻结分析 hash 一致。
- 名义花费 $23.44（父会话 $6.50，control $8.49，treatment $8.45）。

## 预注册判定：`FAIL`

| 条件（§11.7） | 结果 | |
|---|---|---|
| 平均 post_T − post_C ≥ +15 个百分点 | **0.0**（15 对中 T > C 为 0 对，T < C 为 0 对） | ✗ |
| treatment 严格低于 control 的对 ≤ 2 个 | 0 | ✓ |
| treatment 的 FALSE share ≤ control + 10 个百分点 | 12.1% 对 10.0%（+2.1 个百分点） | ✓ |
| 至少一个 Caddy 对 T > C | 0 对 | ✗ |

与盲审无关的两条在盲审之前就已经不成立，因此盲审只补充次要指标，不影响判定。

## 盲审（novel-hop validity）

**审阅依据：model-blind adjudication，不是人工审阅。**

- 找不到独立的人（操作者声明），按 §11.6 的降级规则，由一个全新的 ChatGPT 会话（`GPT-5.6 Sol`，2026-09-30）的审阅作为 primary；没有 secondary，因此不报告一致率。
- 操作者确认该会话是 Temporary Chat，或 memory 已关闭。
- 审阅者只看到审阅表和标签说明，不知道组别、阶段、核验结果和 golden。
- 证据等级弱于独立的人工审阅。

**结果**：35 个审阅单位（Caddy 24，File Browser 11；Authlib 的跳全部匹配 golden，没有 novel 跳）中，TRUE 31 个，FALSE 4 个，INDETERMINATE 0 个。按出现次数，统计范围为各组的最终提交：

| | TRUE | FALSE | FALSE share |
|---|---|---|---|
| 初稿（两组共享） | 49 | 6 | 10.9% |
| control 最终 | 54 | 6 | 10.0% |
| treatment 最终 | 51 | 7 | 12.1% |

**与核验器状态的交叉**（三个阶段合计，按出现次数）：

| 审阅标签 | 核验器 VERIFIED | 核验器 UNVERIFIED |
|---|---|---|
| TRUE | 67 | 87（其中 76 个是 agent 自己声明的 `unsupported`） |
| FALSE | **13**（全部来自一个单位 R016） | 6 |

- **核验器 VERIFIED、审阅判 FALSE 的 13 次，全部是同一个跳**：Caddy head 的 `copyHeaderRoutes = append(…)`（218）→ `goodResponseHandler.Routes = append(…, copyHeaderRoutes...)`（233），`object_composition`。
  - 审阅者的理由：这个 Route 先进入 `copyHeaderRoutes`，之后才经由那次较早的存入到达 `Routes`；而定义明确排除了多步组合。
  - 作者（以及 Codex 在 §14 中）的读法是：218 这条语句定义的对象是切片 `copyHeaderRoutes`，它作为被追加的实参（`copyHeaderRoutes...`）在 233 被存入，而追加进局部切片不是「较早的存入」。
  - 两种读法在冻结定义的文字下都说得通：分歧在于「一步组合」中的「存入」是否包括追加到局部切片。这是**定义层面的歧义**，不是核验器实现与其作者读法不一致。标签按冻结流程保留，不作事后修改。
  - 按审阅者的读法，核验器在这一个跳上接受了一个假跳；按作者的读法则没有。
- 审阅判 FALSE、核验器 UNVERIFIED 的 6 次与核验器一致：
  - R033：`handler`（211）→ `Routes`（233），跨过 218 的两步组合；
  - R006：`MatcherSetsRaw` 作为 `Routes` 写入的 guard；
  - R030（见下）。
- **R030 的语义歧义**：审阅者把一个 `unsupported` 跳判为 FALSE，理由是 `field_flow` 已经能描述这个 link，所以它不是 unsupported。也就是说，审阅者把「relation 标得对不对」也纳入了 FALSE 的判断，而不只是「link 是否成立」。这暴露了 `unsupported` 审阅说明中的一个语义歧义。标签按冻结流程保留，不作事后修改。

## 主要结果

verified golden-hop coverage 如下；located coverage 在每一格都与它完全相同：

| fixture | 初稿（两组共享） | control 最终 | treatment 最终 |
|---|---|---|---|
| Authlib | 100% | 100% | 100% |
| Caddy | 30% | 30% | 30% |
| File Browser | 70% | 70% | 70% |
| 合计 | 66.7% | 66.7% | 66.7% |

- **反馈对 golden 覆盖的影响为零**：15 对中，每一对的初稿、control 最终和 treatment 最终的 verified coverage 完全相同。
- **verified coverage 与 located coverage 处处相等**：agent 只要找到了 golden 位置，关系类型和形式就都是对的，也都被判为 VERIFIED。没有一次失误属于「找到了位置，但给不出可核验的形式」。
- 提案的核验率：初稿 67.0%，control 63.4%，treatment 67.0%。没有被核验的跳大多是 agent 自己声明的 `unsupported`（初稿 88 个跳中有 23 个，多是从挂载处指向运行时 `headers.go` 的跳）。关系类型受支持但没被核验的跳，初稿、control、treatment 分别只有 6、6、4 个。
- `unsupported` 的使用：初稿 23（26%），control 28（30%），treatment 26（29%），两组都没有明显的「改标逃避」。
- **Caddy（严格匹配）**：2/5 个 run 的初稿覆盖了 golden 跳，其中 r3 覆盖全部 4 个，r4 覆盖 2 个 guard 跳。v2 的自然语言路径引用率是 0%，但按 §11.9，这两者不能直接比较，因为关系词表本身就是提示。

## 按 §11.7 事先登记的解读

- 初稿 located coverage 为 66.7%，高于 30%：**不属于**「agent 提不出正确的跳」。
- verified coverage 与 located coverage 相等：**不属于**「agent 找到位置但给不出可核验的形式」。
- 平均增益为 0：属于「**核验反馈基本不起作用**」。

## 事后诊断（在分数冻结之后进行，不改变判定）

1. **失误的形态是遗漏或选了相邻节点，而不是形式错误。** 一次性反馈只对已经提出的跳给出 VERIFIED 或 UNVERIFIED，它对「没有提出的跳」一无所知。所以从结构上说，它无法促使 agent 去发现被遗漏的跳。
2. **严格的节点匹配低估了 agent 实际给出的链。** 如果同一 revision、同一关系、被判为 VERIFIED 的跳，一端正好是 golden 节点、另一端在 golden 节点 ±3 行以内也算上，初稿覆盖从 33/50 提高到 40/50 个 golden 跳槽位：
   - **Caddy 的 2xx guard 在 5/5 个 run 中都被表达成了已核验的跳**。其中 3 个 run 的 guard 锚在 `Match:`（179/181，是 `StatusCode` 的父字段），不是 golden 的 `StatusCode`（180/182）。
   - Caddy 的组合在 r0、r1、r2、r4 中被表达为 `goodResponseHandler := … → rpHandler.HandleResponse = append(…)`（从定义出发）。它被判为 VERIFIED，按单步组合的定义也成立，但与 golden 的出发点（base 198 / head 233 的 `Routes` 写入）相距约 20 行，连上面这个宽松口径也没有算进去。只有 r3 从 `Routes` 写入出发，与 golden 一致。
   - **v2 中从没被引用过的挂载链，在这里的每个 run 中都以已核验的跳的形式出现，只是节点的选择与 golden 不同。**
     - base 侧，5/5 个 run 都给出了三个都被核验的跳：`handler → Routes`（185 → 198）、guard → `Routes` 写入、以及到 `HandleResponse` 的组合。
     - head 侧，4/5 个 run 给出了 `copyHeaderRoutes → Routes`（218 → 233）。盲审把这一跳判为 FALSE（见上面的 R016，属于定义层面的歧义）。r3 给出的 `handler → Routes(233)` 按单步定义不成立，被核验器判为 UNVERIFIED，盲审也判为 FALSE。
   - File Browser r2 从翻转行出发（`ToSlash` / `ReplaceAll` 的重新赋值 → `NameInArchive`）。它也被判为 VERIFIED、也成立，但不是 golden 的出发点（125 的 `TrimPrefix` 定义）。
3. **冻结 scorer 的两个序列化缺陷**，在接收标签时发现，已记入变更记录：
   - YAML 把不加引号的 `TRUE` / `FALSE` 和日期解析成布尔值与 date 对象；
   - 结果是说明中示例格式的标签文件会被当作尚未审阅，日期则让 scorer 在写出结果时崩溃。两者都是 fail closed，从未产生错误结果。
   - 冻结 scorer 没有修改；标签文件在接收时显式加引号，只改语法，标签和备注的内容没有改变。

## 结论的边界

- 15 对、10 个 golden 跳，结论只针对这三个 fixture。
- 形状校验两组共用，所以本实验只测到了**关系层面**反馈的效果（§11.9）。
- 盲审是 model-blind adjudication，没有第二位审阅者；它是较弱的证据。
- 上面的事后诊断是看到结果之后做的，不能用来改写主指标。

## 对后续的含义

- **provider 的作用是过滤，不是引导。** 一次性的 VERIFIED / UNVERIFIED 反馈不会改变 agent 提出什么。
- **节点层面精确的 golden 不适合作为 agent 提案的验收口径**（后续的 §12 已改为链级判据，未重评本实验）。
- **R016 表明，关系定义中「一步」「存入」这类词需要可操作的定义**，否则同一个跳在作者、Codex 和独立审阅者之间会得出不同的真值。它也直接关系到 §14 中 Caddy head 的闭合（见 `results/p-extension.md` 的事后说明）。1A 的关系定义与需求 schema 应当把这类边界写成可检验的规则。

P-Hybrid-2 到此以 **FAIL** 关闭。
