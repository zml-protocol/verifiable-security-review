# §14 P-extension 报告（provider-only；三个当前 fixture 就此退役）

- 冻结 `64ad5e9` → cal 运行一次，分数 `51f4019` → current 运行一次，连同 chain 与判定 `a8f5c90`。两次提交都在查看任何细节之前完成。
- 不调用 LLM。CodeQL 2.27.1；没有任何工具故障。
- 结果文件：
  - `results/p-extension-{dev,cal,current}.json`：逐核验器的分类，以及逐跳状态；
  - `results/p-extension-chain.json`：六个 revision 的链分类；
  - `results/p-extension-decision.json`：判定。

## 预注册判定：`LOOP_CLOSED`

- 判定顺序中的前四条都不成立：
  - `UNSAFE`：没有；
  - `INCONCLUSIVE_TOOL_FAILURE`：没有；
  - `CALIBRATION_BLIND`：没有；
  - `CAPABILITY_GAPS`：没有。
- 三个当前 fixture 的六个 revision，都从早已冻结的 Spike P source 端点出发，经过冻结核验器判为 VERIFIED 的跳，到达 §12 的 terminal，分类为 FULL_CHAIN。Caddy 的链上挂有所需的 guard。

**措辞（§14.6）**：冻结核验器接受了一条从 Spike P source 到 §12 terminal 的链，其中每一跳都是作者写出的已知真跳。这**不**说明漏洞路径已经被端到端证明：
- 链仍然限于可表达的局部证据；
- 需要哪些证据，来自 golden 和作者。

## 留出的 cal（执行留出的校准 / 挑战集，30 跳）

| 核验器 | 分类 | 真跳 VERIFIED | 假跳 VERIFIED |
|---|---|---|---|
| `codeql/go/def_use` | SUPPORTED | 5/5 | 0/2 |
| `codeql/python/def_use` | SUPPORTED | 5/5 | 0/5 |
| `codeql/go/range_element` | SUPPORTED | 2/2 | 0/3 |
| `codeql/go/argument_binding` | PARTIAL | 3/5 | 0/3 |

- **`argument_binding` 漏掉的两个真跳，正是冻结前在真值中注明的盲区**：
  - 局部函数值的调用（c11）；
  - 接口分派（c20）。
  - 它是一个**复合 relation**：静态调用目标，加上按位置的实参绑定。这里的 PARTIAL 是对这个复合 relation 的描述，不能拆成「跨函数调用」与「实参绑定」两项能力分别计功。
- **没有真跳被判为 CONTRADICTED**。被形状检查判为 CONTRADICTED 的 3 跳全是假跳（2 个 reversed，1 个单变量 range 的索引变量）。其余 10 个假跳都是 UNVERIFIED。

## current（三个当前 fixture，95 跳：15 真 80 假）

| 核验器 | 分类 | 真跳 VERIFIED | 假跳 VERIFIED |
|---|---|---|---|
| `codeql/go/def_use` | SUPPORTED | 5/5 | 0/23 |
| `codeql/python/def_use` | SUPPORTED | 4/4 | 0/20 |
| `codeql/go/argument_binding` | SUPPORTED | 2/2 | 0/10 |
| `codeql/go/range_element` | SUPPORTED | 2/2 | 0/8 |
| `codeql/go/object_composition`（P-Hybrid-1，冻结） | SUPPORTED | 2/2 | 0/10 |

- **假跳（按变异规则）**：

  | 变异规则 | 数量 | 结果 |
  |---|---|---|
  | shift | 30 | 全部 UNVERIFIED |
  | wrong_target | 26 | 全部 UNVERIFIED |
  | reversed | 15 | 14 个被形状检查判为 CONTRADICTED；k1-h-reversed 两端都是定义，形状成立，为 UNVERIFIED |
  | wrong_revision | 9 | 全部被引用检查拦下，符合预期 |

- **关键的安全挑战成立**：`handler`@211 → `Routes`@233（k2-h-shift-up）跨过了 218 这一步真实的中间组合，被判为 UNVERIFIED。冻结的 `object_composition` 没有把两步组合当成一步。
- 按关系名合并的汇总（`report_only_by_relation`）是 **report-only aggregate**，不是校准单位，也没有进入判定。

## 六条链

| fixture | revision | 边数 | 桥跳 | 局部（golden） |
|---|---|---|---|---|
| Authlib | base / head | 4 | 参数 `s` → `to_bytes` → `deserialize_compact` 调用（2 × `def_use`） | 2 |
| Caddy | base | 2 | `handler` → `Routes` 写入（`object_composition`） | 1，另挂 guard |
| Caddy | head | 3 | `handler` → `copyHeaderRoutes`（`def_use`）→ `Routes` 写入（`object_composition`） | 1，另挂 guard |
| File Browser | base / head | 5 | `filenames` → `fname`（`range_element`）→ 实参（`def_use`）→ 形参 `path`（`argument_binding`）→ `nameInArchive`（`def_use`） | 1 |

## 过程中的更正（冻结之前）

起草时，我曾把 Caddy head 当作能力缺口，打算预注册。核对冻结的 P-Hybrid-1 `Definition`（包括 `v = e`）后发现：
- 211 → 218 按 `def_use` 为真；
- 218 → 233 按冻结的 `object_composition` 为真；
- 因此不需要任何新关系。

这个更正发生在任何桥查询接触 current 之前，经 Codex 审查，并保留了 211 → 233 这一负例。

## 事后说明：Caddy head 的闭合依赖一个有争议的真值（不改变判定）

§14 的结果提交之后，P-Hybrid-2 的盲审（model-blind adjudication，全新的 ChatGPT 会话，没看过 §14）审阅了**同一个跳**：Caddy head 的 `copyHeaderRoutes = append(…)`（218）→ `goodResponseHandler.Routes = append(…, copyHeaderRoutes...)`（233），`object_composition`，也就是这里的 k2-h。审阅者按同一份冻结定义，把它判为 **FALSE**。

- **审阅者的读法**：Route 先进入 `copyHeaderRoutes`，之后才经由那次较早的存入到达 `Routes`；而定义排除多步组合。
- **作者与 Codex 的读法**（§14 冻结的真值）：218 定义的对象是切片 `copyHeaderRoutes`，它作为被追加的实参在 233 被存入；追加进局部切片不算「较早的存入」。
- 起草 §14 时，我最初的判断与审阅者一致，曾打算把 Caddy head 预注册为能力缺口。后来改为作者读法，并经 Codex 审查。

**§14 的判定不变**：真值在运行之前冻结，不因事后审阅重评。但报告必须写明：

- 六个 revision 的闭合中，**Caddy head 这一条依赖一个在独立审阅中有争议的真值**。
- 按审阅者的读法，没有冻结关系能表达 218 → 233 这一步，Caddy head 是能力缺口，闭合的是六个中的五个。
- 这是冻结定义中「一步组合」「存入」的歧义，不是核验器实现与其作者读法不一致。1A 的关系定义应当把这类边界写成可检验的规则。

## 局限

- 跳由了解代码和 golden 的作者写出。这里测的是**核验器能否接受并闭合已知的证据**，不是发现能力。
- 负例是从真跳系统变异出来的相关挑战，不是随机样本。「0 个假跳被判为 VERIFIED」只描述本集合。
- 语言覆盖不对称，按 fixture 需求决定：
  - Python 只有 `def_use`；
  - `argument_binding` 与 `range_element` 只有 Go 版；
  - `argument_binding` 只跟随静态解析，接口分派和函数值是盲区；
  - 值流只在函数内。

## 对整条分支的含义

把 §12、§13、§14 放在一起看：
- **组链**：在冻结的局部核验器与连接器下，agent 经常能组成完整的已核验链（§12：18/30）。
- **补链**：给出由 golden 导出的证据陈述时，初稿大多已经完整（§13）。
- **接到真实入口**：用三个通用 relation，冻结核验器能把真实入口接到这些局部链上，六个 revision 全部闭合，且没有观察到误核验（§14）。其中 Caddy head 的闭合依赖一个在独立审阅中有争议的真值（见上面的事后说明）。

**剩下没有回答的，是「需要哪些证据」本身。** 这正是下一步在新 fixture 上做 1A 泛化要正面面对的问题：结构化的证据需求发现，在实现之前锁定需求，并且不给 agent 看冻结的需求规格。

## 三个当前 fixture 退役

Authlib、Caddy、File Browser 从此不再用于新的研究设计或 agent 行为实验。已冻结流程中剩下的 P-Hybrid-2 盲审也已完成：以 model-blind adjudication 作为 primary，P-Hybrid-2 以 FAIL 关闭（`results/p-hybrid-2.md`）。
