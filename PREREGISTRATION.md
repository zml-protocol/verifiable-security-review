# 预注册：secreview kill experiments（protocol v1）

> **状态：已锁定。** 本文件首次提交的 commit 哈希就是预注册时间戳。之后对本文件的任何修改都要记入文末的「变更记录」，写明日期和理由。
>
> **改协议必须升版本。** prompt、工具、推导规则、runner 参数，这四样里任何一样变了，就是新的 protocol 版本（`experiments/agent_verify/run.py` 里的 `PROTOCOL`）。新版本要重新预注册；不同版本的 run 放在不同目录，结果**不混算**。
>
> **pilot 不计入。** `runs/pilot/2026-09-27-haiku-smoke/` 是在预注册之前做的 1 次工具链冒烟（Haiku，H1 forward），不计入任何指标。

## 0. 要回答的问题

| 编号 | 风险假设 | 如果不成立 |
|---|---|---|
| 1A | 结构候选（Trailmark graph-evolution）在普通 PR 上的信噪比可以接受 | 后面的 agent 全在给噪声做分诊 |
| 1B | agent 能针对同一个 hypothesis，在 base 和 head 上分别、正确地取证 | 反事实归因这个核心不成立 |
| 1C | 能写出「在 head 上因断言失败、在 base 上通过」的差分测试 | REFUTED 没有现实来源，REGRESSION 这一级不存在 |

**范围**：这一轮只评估 Claude。Codex 关不掉 shell，隔离条件和 Claude 不对等，不在 v1 范围内；runner 里的 `codex_cmd` 保留，但不跑、不计入。

### 决策矩阵

| 结果 | 决定 |
|---|---|
| 1A、1B、1C 都通过 | 按完整架构推进（Phase 2：正式 schema） |
| 1A、1B 通过，1C 不通过 | 产品只承诺 `CHANGE_IMPLICATED`，不承诺 `REGRESSION` |
| 1B 通过，1A 不通过 | 放弃 Trailmark 结构候选作为主要 hypothesis 来源，重新评估 generator |
| 1B 的归因正确率达标，但证据完整率很低 | agent 只是在根据 diff 形状猜结论，按 1B 不通过处理 |
| 1B 不通过 | 停止。核心假设不成立 |

---

## 1. 冻结的实验配置（protocol v1 / v1.1）

| 项 | 值 |
|---|---|
| 协议版本 | v1 用于第一次阶段 1；阶段 1 复验和阶段 2 用 **v1.1**。面向 agent 的 harness 部分（prompt、11 个工具的实现，即 `src/spike/`）与 v1 相同，相对锁定 commit `f623da3` 的 `git diff` 为空；hypothesis 内容属于 fixture，不在比较范围内。v1.1 在 runner 里改了三处：启动预算守卫（§3.6）；按指定 slot 运行；**agent 的工作目录改为 harness 仓库之外的临时空目录**（见 §2.1 的上下文泄露不变量） |
| agent 运行时 | Claude Code CLI 2.1.280，`claude -p` |
| 隔离参数 | `--tools ""` `--strict-mcp-config` `--allowedTools mcp__secreview` `--setting-sources ""` `--no-session-persistence`，工作目录为空 |
| prompt | `experiments/agent_verify/prompt.md` |
| 工具（11 个） | get_task、list_files、read_code、search_code、find_symbol、changed_files、diff_file、map_location、submit_observation、submit_blind_spot、finish |
| 推导规则 | `src/spike/derive.py`（规则见 §1.1） |
| 期望答案推导 | `src/spike/golden.py` |
| 条件 | `forward`、`swapped`、`identity_base`、`identity_head` |
| 重复次数 | 每个 (hypothesis, 条件) 跑 5 次，各次相互独立 |

### 模型

| 用途 | 模型 | effort | 单次花费上限 |
|---|---|---|---|
| 阶段 1：synthetic 热身（harness 资格验证） | `claude-haiku-4-5-20251001` | 不适用（该模型不支持 effort） | $1 |
| 阶段 2：真实语义 fixture（主结果） | `claude-sonnet-5` | `high` | $3 |

- Haiku 4.5 的退役时间是「不早于 2026-10-15」，阶段 1 必须在这个日期之前跑完。
- 主结果选 Sonnet 5 而不是 Sonnet 4.6：它是当前这一代的 Sonnet，价格更低（$2/$10 对 $3/$15），退役不早于 2027-06-30。另外，它的 knowledge cutoff（2026 年 1 月）早于三个真实 CVE 的公开日期，详见 §3.3。

### 1.1 推导规则

**组件状态**：只看某个 revision 上某个组件的观察，`unclear` 不计入。

| 有效观察 | 状态 |
|---|---|
| 只有 supports | supported |
| 只有 contradicts | contradicted |
| 两种都有 | conflicted |
| 没有 | no_evidence |

**revision 状态**：各组件取合取，按下面的顺序判定。
1. 任一组件是 contradicted → `CONTRADICTED`
2. 任一组件是 conflicted → `CONFLICTED`
3. 全部组件是 supported → `SUPPORTED`
4. 部分组件是 supported → `INCOMPLETE`
5. 否则 → `NO_EVIDENCE`

`CONTRADICTED` 只是 agent 层面的反对意见，**不等于 REFUTED**。

**归因（只用静态证据）**

| head | base | implicated | 结果 |
|---|---|---|---|
| SUPPORTED | SUPPORTED | – | `PRE_EXISTING` |
| SUPPORTED | CONTRADICTED | 是 | `CHANGE_IMPLICATED` |
| SUPPORTED | 其他 | – | `UNATTRIBUTED` |
| CONTRADICTED | SUPPORTED | 是 | `FIX_IMPLICATED` |
| CONTRADICTED | 其他 | – | `NOT_SUPPORTED` |
| 其他 | – | – | `UNDETERMINED` |

**implicated** 成立的条件：某个组件在 base 和 head 之间发生了 supported ↔ contradicted 的翻转，并且该组件至少有一条有效引用与改动行重叠。改动行指零上下文 diff 的 hunk，在各自一侧计算。

按这个定义，identity 条件（两边是同一个 commit）下改动行为空，runtime **不可能**推导出 `CHANGE_IMPLICATED`。所以「identity 条件下错误归因」不是一个有意义的指标，identity 条件要看的是 §4 里的组件一致性和措辞筛查。

### 1.2 run 的有效性与重跑

每个 (hypothesis, 条件, 重复编号) 是一个 slot。runner 执行过一次后，由 `experiments/agent_verify/validity.py` 判定 slot 的有效性。

| 判定 | 情形 | 处理 |
|---|---|---|
| `INFRA_INVALID` | MCP server 没有启动；agent CLI 没有启动；API/网络错误导致中止（result 事件里出现 API Error、overloaded、5xx、rate limit、连接错误）；CLI 崩溃；超时并且一次工具调用都没有发生 | 可以重跑 |
| `VALID` | 其他所有情形，包括正常结束、预算耗尽（`error_max_budget_usd`）、轮次耗尽、有工具调用之后的超时、模型拒绝（`refusal`）、没有调用 finish、反复提交无效引用之后仍然没有改对 | 按现状计分，**不得重跑** |

- **重跑**：只用 `--rerun-invalid` 触发。每个 slot 最多尝试 3 次（原始 1 次加重跑 2 次）。重跑沿用同一个重复编号；失败的那次改名为 `r<k>.invalid<n>` 保存，不删除。
- **3 次都失败**的 slot 仍记为 `INFRA_INVALID`，从指标的分母中剔除，但要在报告里列出。如果 `INFRA_INVALID` slot 占比超过 5%，按 harness 故障处理（§2.1）。
- **拒绝属于真实的产品行为**：Sonnet 5 默认启用了网络安全方面的 safeguard，防御性的安全审查也可能被拒绝。拒绝按 `VALID` 计入结果，不算基础设施故障。
- **没有调用 finish 的 VALID run**，按它已经被接受的观察来推导和计分。

### 1.3 可追溯性

- runner 发现工作区有未提交的改动时**拒绝运行**，除非显式传入 `--allow-dirty`。带这个参数的 run 不属于预注册范围。
- 每次 run 的 `meta.json` 记录以下内容：protocol 版本；尝试次数；harness 的 commit，以及工作区是否有改动；`src/spike/*.py`、`run.py`、`prompt.md` 各自的 sha256（MCP 工具的 schema 由 `mcp_server.py` 和 `session.py` 决定，因此已经包含在内）；CLI 版本；模型、effort、单次花费上限、超时；base/head 的 commit 和 tree SHA。
- Claude Code 自身的完整系统提示无法取得哈希，只能靠固定 CLI 版本来保证一致。
- scorer 从 agent 的事件流里记录 **API 实际返回的模型标识**（`served_models`）。输出的汇总里还会记录 scorer 的 sha256、golden 的 sha256，以及 harness 的 commit。

### 1.4 先冻结分数，再看 transcript

每个阶段的矩阵跑完后，**第一次人工查看任何 transcript 之前**，先运行 `score.py --out results/<阶段>.json`，并把这份汇总提交到 git。这份汇总包含每一次 run 的得分和评分所用的来源信息。之后因为发现 harness bug 而做的任何修改，都不能改写这份已经提交的结果。

---

## 2. 阶段 1：synthetic 热身（Haiku，80 次）

`synthetic-notes` 的 4 个 hypothesis × 4 个条件 × 5 次 = 80 次，预计花费约 $6。

**目的是验证 harness 本身**，而不是评估模型能力。

### 2.1 harness 硬不变量（任何一项不为 0，都是基础设施 bug）

| 不变量 | 要求 |
|---|---|
| 被接受的 anchor 重新读取后哈希对不上（`anchor_audit_failures`） | 0 |
| 被接受的观察引用了另一侧 revision 的 anchor（`accepted_revision_mismatches`） | 0 |
| 调用了 secreview 以外的工具（`runs_with_foreign_tools`） | 0 |
| 工具层内部错误（`harness_errors`：`internal_error`、`git_error`） | 0 |
| 上下文泄露（`runs_with_context_leak`）：agent 的工作目录位于 harness 仓库内，或 auto-memory 目录不为空 | 0 |
| 对同一批 run 重新评分，结果出现差异（`scored_at` 除外） | 0 |
| 重跑之后仍为 `INFRA_INVALID` 的 slot 占比（`infra_invalid_rate`） | ≤ 5% |

agent 在**尝试**阶段的引用错误（`quote_ambiguous`、`revision_mismatch` 等被拒绝后又改对的）是协议正常工作的表现，不算失败，只记录比例。

### 2.2 协议合理性门槛

| 指标 | 门槛 |
|---|---|
| 归因正确率（全部条件） | ≥ 90% |
| 证据完整且归因正确率 | ≥ 80% |
| swap 镜像一致性 | ≥ 90% |
| identity 不一致率（run 级：任一组件在两侧状态不同，这个 run 就算不一致；40 次 identity run 里最多 2 次） | ≤ 5% |
| 负对照假 SUPPORTED 率 | ≤ 10% |

### 2.3 处理规则

- 先按 §1.4 冻结分数。
- **不变量失败** → 修 harness，版本升为 v1.1，记入变更记录，然后重跑阶段 1。
- **门槛失败** → 先阅读失败的 run，再用 Sonnet 5 跑同样的 80 次：
  - Sonnet 5 通过 → 失败归因于 Haiku 的能力，进入阶段 2；
  - Sonnet 5 也不通过 → 协议有问题，改成 v2 并重新预注册。
- **模型下线兜底**：如果 Haiku 4.5 在阶段 1（含 v1.1 重跑）完成之前下线，阶段 1 改用 `claude-sonnet-5`（effort `high`）执行，门槛不变，并记入变更记录。
- 无论结果如何，都**不修改**本节的门槛。

### 2.4 阶段 1 在 v1.1 下复验

v1 的阶段 1 全部 80 个 run 都违反了事后补上的上下文泄露不变量。原因是 agent 的工作目录是 `runs/agent_verify/v1/<case>/<hyp>/<condition>/…/cwd`，而 Claude Code 会把工作目录、git 状态和最近的 commit 写进系统提示，因此条件名（`swapped`、`identity_head`）和 case id 都可能被 agent 看到。在 agent 可见的输出里，没有一个 run 提到过这些字符串；但 Haiku 没有可见的思考过程，不能排除它们暗中产生了影响。按 §2.3「不变量失败则修 harness、升版本、重跑阶段 1」的处理规则，在 v1.1 下用同样的模型、同样的 80 个 slot、同样的门槛重跑阶段 1，通过后才进入阶段 2。v1 的结果（`results/1b-stage1-haiku.*`）保留，报告里标注这个问题。

---

## 3. 阶段 2：真实语义 fixture（Sonnet 5）

### 3.1 fixture（引入 commit 已通过本地克隆核实）

| id | 语言 | CVE | base（引入 commit 的父 commit） | head（引入 commit） | 考察点 |
|---|---|---|---|---|---|
| S1 `authlib-jws-none` | Python | CVE-2026-28802 | `21f7f50820f3` | `a61c2acb8074` | 一行改动（`NoneAlgorithm.verify` 从恒 False 改为 `sig == b""`）改变了安全语义，调用图帮不上忙 |
| S2 `caddy-forward-auth` | Go | CVE-2026-30851 | `00f948c6056f` | `05cfb121ec3f`（PR #6608，squash） | 身份 header 的来源和信任绑定：只有认证服务返回的值才可信，而不是 source→sink |
| S3 `filebrowser-archive-backslash` | Go | CVE-2026-62843（以及该 commit 修掉的 CVE-2026-54093） | `0231b7ebdfbe` | `847d08bdd135` | 安全修复本身引入了回归；同一个 commit 还顺带修了另外两个问题 |

- **S1 的 advisory 有两处不一致。** advisory 标注的受影响范围是 ≥1.6.5，但正文说升级到 1.6.0 就出现了问题，而 `a61c2ac` 最早包含在 v1.6.0 里。advisory 用的措辞也只是「likely introduced」。所以 S1 的 golden 真值必须先做差分执行核实（在 base 和 head 上分别跑 advisory 里的 PoC）。
- **正式计分的 hypothesis 共 8 个**（原计划的标签已被执行真值修正，见 §3.5）：

| fixture | hypothesis | base / head | 期望（静态） | 期望（执行） |
|---|---|---|---|---|
| S1 | H1：默认 decoder 接受 `alg:none` + 空签名 | 否 / 是 | CHANGE_IMPLICATED | REGRESSION |
| S1 | H2（负对照）：`alg:none` + 非空签名 | 否 / 否 | NOT_SUPPORTED | NOT_SUPPORTED |
| S2 | H1：认证响应缺 `X-User-ID` 时，客户端的值到达 upstream | 否 / 是 | CHANGE_IMPLICATED | REGRESSION |
| S2 | H2（负对照）：认证响应带 `X-User-ID` 时，客户端的值到达 upstream | 否 / 否 | NOT_SUPPORTED | NOT_SUPPORTED |
| S3 | H1：朴素 POSIX 解压越界 | 否 / 是 | CHANGE_IMPLICATED | REGRESSION |
| S3 | H2：条目名带反斜杠分隔符 | 是 / 否 | FIX_IMPLICATED | FIXED |
| S3 | H3（陷阱）：朴素 Windows 解压越界 | 是 / 是 | PRE_EXISTING | PRE_EXISTING |
| S3 | H4（负对照）：不含 `..` 的反斜杠文件名越界 | 否 / 否 | NOT_SUPPORTED | NOT_SUPPORTED |

- S1 的探针 T3（只允许 RS256 的 decoder）保留在 `truth/` 里作为**不计分**的负对照：它考察的是配置边界，离改动的语义较远，T2 已经直接约束 `sig == b""`。

### 3.2 暂缓的 fixture（v2 再考虑）

- **Gogs CVE-2026-52806**：还没定位到引入 unsafe rebase 调用的具体 commit。
- **Open WebUI `2054ee0`（PR #22109）**：作为「不要错误归因」的困难案例。这个 PR 修了一部分资源类型，但留下了原本就存在的缺口，期望结果是 `PRE_EXISTING` 或 `UNATTRIBUTED`。前提是先核实 base 上本来就有这个漏洞。

### 3.3 记忆污染

三个 advisory 的公开日期分别是 2026-03-04、2026-03-06、2026-07-20，都晚于 Sonnet 5 的 knowledge cutoff（2026 年 1 月）。

这只能说明**模型记住「这段代码有漏洞」这一安全标签的风险降低了**，并不能排除训练数据污染：S2 的引入 PR 是 2024 年的，S1 的引入 commit 是 2025 年的，模型可能见过这些代码，只是当时还没有安全标签。S3 的引入 commit（2026-06-03）本身就晚于 cutoff，风险最低。

就这个 spike 的目的而言，这样的风险可以接受，阶段 2 不另设对照 case。以后如果换用 knowledge cutoff 在 2026 年 6 月的模型（Opus 5.5、Fable 5.1），S1 和 S2 的 advisory 已经早于 cutoff，需要重新评估。

### 3.4 hypothesis 与 golden

- 每个 fixture 至少包含 1 个真 hypothesis，以及 1 个落在改动附近的负对照。
- **golden 必须在该 fixture 的第一次 agent run 之前写完并提交。**
- golden 的真值能用差分执行核实的，一律核实。执行由人来做，不由 agent 做；这一步同时也是 1C 的可行性预检。
- **证据按「事实」评分，不按某一个 anchor 评分。** golden 的 `facts` 里每条事实都写出所有已知的充分证据集（`evidence_sets`）。命中其中任意一个证据集就算覆盖了这条事实；一个证据集里的所有位置都必须被引用。只要求 revision 和位置对上，不要求 agent 把引用归在哪个组件下（组件判断由组件准确率单独衡量）。
- **golden 修订**：人工复查时，如果发现 agent 引用了 golden 没列出、但同样充分的证据，只允许**新增**一个证据集，不得修改真值、组件状态或归因。修订要记入变更记录，对全部 run 重新评分，报告里同时给出修订前后两组数字。

- **必需事实的选取原则**（写 golden 时逐条检查）：
  1. 只覆盖三类事实：base 的关键行为、head 的关键行为，以及证明这些行为确实位于攻击路径上的**最短可达路径**。
     - 在主张成立的一侧，必须证明关键行为可达。
     - 在主张不成立的一侧，如果反证依赖某个**保护动作被执行**（检查拒绝、Set 覆盖、签名校验失败），同样要证明这个动作在路径上；否则路径不可达时，主张反而可能成立。
     - 只有当反证是「危险成分在任何路径上都不会产生」时，才可以省略路径。
     - 本阶段的 8 个 hypothesis 逐一检查过，没有一个属于可以省略的情形，所以每一侧都要求路径事实。
  2. base 和 head 完全相同的背景机制，除非它是因果链里不可缺少的一环，否则不要求引用。
  3. 协议常识、攻击者能力之类写成 hypothesis 的前提，不当作「代码事实」。
  4. 不要求完整调用链，也不奖励冗余引用。
  5. 反事实检验：删掉某条事实后，如果剩下的事实仍足以从仓库证据推出真值，这条就不应该是必需事实。
  6. 不充分的捷径只写进 golden 的 `notes` 作为文档，不参与评分。
- **golden 的独立审查**：golden 冻结之前，由另一个模型（Codex）独立审查必需事实。审查时不能看任何 Sonnet 的输出（此时也还没有任何 Sonnet 输出）。

### 3.5 执行真值

三个 fixture 的真值都来自 base/head 对称执行。脚本、探针和结果放在 `fixtures/<case>/truth/`，与 golden 一起冻结。

| fixture | 执行方式 | 环境 |
|---|---|---|
| S1 | `truth/verify.sh`：把两个 commit 各装进一个独立 venv，运行同一个 `poc.py`（T1、T2、T3） | Python 3.12.13，cryptography 45.0.7 |
| S2 | `truth/verify.sh`：用同一个最小宿主程序在两个 commit 上编译 Caddy，接同一个认证桩和回显 upstream，发同样的三组请求 | Go 1.26.8（sha256 已校验，装在项目本地），`GOTOOLCHAIN=local`，`GOFLAGS=-mod=readonly`，`CGO_ENABLED=0` |
| S3 | `truth/verify.sh`：把同一个 `truth_probe_test.go` 放进两个 commit 的 `http/` 包，按 `rawDirHandler` 的步骤执行（`parseQueryAlgorithm` 选择归档器 → `getFiles` → 用锁定版本的归档器真实写出 zip 和 tar），再从归档字节里读回条目名。只有「解压」这一步是模型：按 `/` 切分（POSIX），或按 `/` 和 `\` 切分（朴素 Windows），不做 `..` 清理 | 同上 |

- **最小宿主规则**：如果 base 和 head 的标准构建都因为与目标改动无关的既有依赖冲突而失败，可以在观察任何探针结果之前，改用同一个最小宿主程序。两侧的宿主代码、构建参数和依赖必须相同，不得修改被测模块，也不得改变依赖解析结果。S2 按这条规则执行：上游在这段时间里 go.mod 同时钉住了 otel/sdk v1.21.0 和 otel/trace v1.29.0，标准构建不通过（后来由 #6676 修复）。因此 S2 的执行真值证明的是：**在两侧完全相同的宿主程序下，未修改的相关 Caddy 模块发生了行为翻转**。它不证明「官方标准二进制端到端复现」。
- **方法修正记录**：Go 的模块模式最初设成了 `-mod=mod`。在任何真值定下来之前，已统一改成 `-mod=readonly`；S3 重跑后结果与之前逐项一致。
- **执行结果修正了原计划的标签**：`847d08b` 只把反斜杠替换成 `/`，没有加任何 `..` 检查。`..\..\evil.sh` 在 head 上变成 `../../evil.sh`，对朴素的 Windows 解压器依然越界。所以 CVE-2026-54093 能写成 FIX_IMPLICATED 的只有「条目名不再带反斜杠」这一个窄主张（H2）；「Windows 解压越界」在 base 和 head 上都成立（H3，PRE_EXISTING）。

### 3.6 预算

- **启动预算规则**：Sonnet 评估的名义预算为 $200，包括最初 5 个正式 run。每启动一个 run 之前，runner 为这个 run 以及所有正在运行的 run 各预留单次预算（$3）。只有当「已观测花费 + 进行中 run 的预留 + 新 run 的预留」≤ $200 时，才启动新的 run。这个决定不得使用任何与结果有关的信息。
- **这是启动上限，不是计费上限**：底层 CLI 只在两轮对话之间检查自己的 `--max-budget-usd`，一个已经启动的 run 可能超过它的预留。因此 $200 只约束启动，不能保证账单不超过 $200。任何末端超支都会作为 harness 局限明确记录（`meta.json` 里的 `cost_usd` 和 `overshoot`）。
- **花费的定义**：CLI 在每个 run 的 result 事件里报告的 `total_cost_usd`（按 API 标价折算）。所有尝试都计入，包括被判定为 INFRA_INVALID 的尝试。runner 打开 `agent.jsonl` 那一刻起，这次尝试就开始计费；没有报告花费的尝试按单次预算 $3 计，即使它在写出 `meta.json` 之前就退出了。进行中的尝试只按预留额度计算，不重复计算。
- **计费方式**：阶段 1 的 init 事件显示 `apiKeySource: none`，即使用 claude.ai 订阅登录，没有 API key。因此 $200 是按 API 标价折算的名义额度；实际的限制来自订阅用量，超出时表现为 rate limit，按 §1.2 判为 INFRA_INVALID。提供方那一侧没有强制的硬上限。每个 run 的 `meta.json` 会记录 `api_key_source`，不记录任何凭据。
- **前 5 个正式 run（gate）**：见 `experiments/agent_verify/stage2_gate.txt`，在第一次调用 Sonnet 之前固定，按以下顺序、`--jobs 1` 执行，全部计入正式数据：
  1. `authlib-jws-none/H1/forward/r0`
  2. `caddy-forward-auth/H1/forward/r0`
  3. `filebrowser-archive-backslash/H1/forward/r0`
  4. `filebrowser-archive-backslash/H3/forward/r0`
  5. `caddy-forward-auth/H2/forward/r0`
- **预算推算与裁剪**（`experiments/agent_verify/budget.py plan`，只读取计费字段，从不打开 state、transcript 或分数）：
  - 每个 gate slot 的校准花费是它**所有尝试的花费之和**（包括重跑）。单次花费的估计值取 5 个 slot 中的**最大值**，再加 10% 余量。
  - 如果连 1 次重复都放不下，推算结果是 STOP：gate 之后的所有 slot 都记为 budget-censored。
  - 设计规模为 8 个 hypothesis × 4 个条件 × 5 次 = 160 个 slot。如果「已花费 + 剩余 slot × 单次估计」超过 $200：先删除整个 `identity_base` 条件；仍然超出，就对所有剩余单元**同步**每轮减少 1 次重复，直到不超出为止。
  - 不得单独删除某个 fixture、hypothesis 或条件（`identity_base` 除外），也不得根据观察到的效果调整重复次数。
- **被裁掉的 slot** 记为 budget-censored（`budget_plan.json`）；启动守卫拒绝的 slot 记入 `budget_censored.jsonl`。这两类都不算失败或缺失数据，在报告里单独列出。

### 3.7 门槛

| 指标 | 通过 | 终止 |
|---|---|---|
| harness 不变量（同 §2.1） | 0 | 大于 0 就先修 harness |
| forward 归因正确率（全部 fixture 合计） | ≥ 80% | < 50% |
| 每个真 hypothesis（至少一侧为真）各自在 forward 条件下归因正确的 run 所占比例（重复次数被裁剪时按比例计算） | ≥ 60% | 任一真 hypothesis 为 0% |
| 证据完整且归因正确率 | ≥ 60% | < 40%（同时归因正确率 ≥ 80% 时，视为在猜） |
| 负对照假 SUPPORTED 率 | ≤ 10% | > 25% |
| swap 镜像一致性 | ≥ 80% | < 60% |
| identity 不一致率（run 级） | ≤ 10% | > 25% |
| 系统性 revision 混淆（某个 fixture 有超过 50% 的 run 出现过尝试阶段的 revision_mismatch） | 0 个 fixture | ≥ 2 个 fixture |

---

## 4. 指标定义（与 `experiments/agent_verify/score.py` 的字段对应）

| 指标 | 字段 | 定义 |
|---|---|---|
| 归因正确率 | `attribution_correct_rate`（以及 `_forward`） | 推导出的归因与该条件下期望归因一致的 run 所占比例 |
| 证据完整且归因正确率 | `evidence_complete_correct_rate` | 归因正确，**并且** golden 的每条事实都被覆盖的 run 所占比例 |
| 事实覆盖率 | `fact_coverage`（以及 `_by_condition`） | 被覆盖的事实所占比例（覆盖的定义见 §3.4） |
| 负对照假 SUPPORTED 率 | `negative_control_false_supported_rate` | 负对照 hypothesis 的 run 中，任一 revision 被推导为 SUPPORTED 的比例 |
| 假 SUPPORTED revision 率 | `false_supported_revision_rate` | 所有期望为非 SUPPORTED 的 (run, revision) 中，被推导为 SUPPORTED 的比例 |
| 重复一致性 | `repeat_agreement` | 每个格子里多数归因所占的比例，再取平均 |
| swap 镜像一致性 | `swap_mirror_consistency` | 按 (组件, 侧) 比较：swapped 的多数状态与 forward 对侧的多数状态一致的比例。重复之间相互独立，**不按重复编号配对** |
| identity 不一致率 | `identity_inconsistency_rate` | identity 条件下，至少一个组件在两侧状态不同的 run 所占比例（门槛看这个） |
| identity 组件一致率 | `identity_component_agreement` | identity 条件下，两侧状态相同的组件所占比例。只报告 |
| identity 措辞筛查 | `identity_runs_with_change_language` | identity 条件下，陈述里出现「移除、引入、改动……」一类措辞的 run 数。**只作诊断，不设门槛**，用来筛选需要人工阅读的 run |
| 基础设施无效率 | `infra_invalid_rate` | 重跑之后仍为 `INFRA_INVALID` 的 slot 所占比例，上限 5%（§1.2） |
| 尝试阶段引用错误率 | `attempt_citation_error_rate` | 被拒绝的引用次数 ÷ 提交次数 |

**人工分析**（结论要写进报告，不设门槛）：

1. identity 条件下失败或被措辞筛查标出的 run，逐个归入四类之一：编造代码差异 / 编造语义差异 / 引用了错误 revision 的证据 / 没有依据的因果措辞。
2. forward 和 swapped 各自的事实覆盖率。两者都高，才说明镜像一致不是巧合。
3. 归因正确、但事实没有全部覆盖的 run 要逐个复查，确认是 agent 没找到证据，还是 golden 漏列了充分证据（后者按 §3.4 修订）。

---

## 5. 1A：结构候选的信噪比

- **普通 PR 样本**：从 S1–S3 这三个仓库中取已合并的 PR，只保留改动了入口可达代码的 PR（PR 改动的函数，在 base 或 head 的 Trailmark 图里能从某个 entrypoint 到达）。目标 60 个，其中有意放入至少 15 个以重构为主的 PR。【待定：抽样窗口】
- **known-regression 样本**：把安全修复 commit 反过来用，base 取修复后，head 取修复前。只选改动不超过 50 行、并且不夹带重构的修复。
- **标注**：由单人标注，标注人事先不知道该 PR 是否与安全有关。每个候选标为「值得跟进 / 看着合理但无害 / 纯噪声」。

| 指标 | 通过 | 终止 |
|---|---|---|
| 每个 PR 的候选数中位数 | ≤ 1 | > 3 |
| 有候选的 PR 所占比例 | ≤ 30% | — |
| 「值得跟进」所占比例 | ≥ 20% | < 5% |
| known-regression recall | ≥ 50% | < 20% |
| 只由重构或符号移动引起的候选比例、unresolved 边比例 | 只报告 | — |

## 6. 1C：差分测试

- **fixture**：首选 S1 Authlib（纯 Python，advisory 自带 PoC 可以作为参照）。备选 S2 Caddy。
- **判定成功**：测试在 head 上**因为断言而失败**（编译错误、导入错误不算），并且在 base 上通过。
- **负对照**：对负对照 hypothesis 做同样的流程，「成功」次数必须是 0。
- **门槛**：5 次中至少 3 次成功算通过；0 次成功则终止。
- **环境**：断网容器，不挂载宿主目录。

## 7. 已知局限

- `claude -p` 会带上 Claude Code 自身的系统提示。为此固定了 CLI 版本，升级 CLI 等同于改协议。
- 版本号文件（如 go.mod、pyproject）无法屏蔽。
- `find_symbol` 用的是正则启发式。
- 1A 只有单人标注。
- synthetic-notes 由我们自己编写，难度偏低。

## 8. v2：显式路径引用（同期 A/B）

**背景**：v1.1 的阶段 2 按预注册判为不通过（`results/1b-stage2-sonnet5.md`），失分集中在路径事实上。v2 只检验一个问题：**在 prompt 里明确要求引用路径，能否把证据完整率提上来，同时不损害归因。** v1.1 的数据不参与 v2 的任何统计，只作为历史结果。

### 8.1 冻结的配置

| 项 | 值 |
|---|---|
| 协议 | v2 = v1.1 加上 v1.2 修复（`git grep` 拒绝的非法正则改为输入错误 `bad_pattern`），再加上 prompt 分组 |
| 不变的部分 | 模型 `claude-sonnet-5`、effort `high`、Claude Code 2.1.280、11 个工具、隔离的工作目录；golden、必需事实、推导规则与 v1.1 冻结版本（`0a96a96`）逐字节相同；scorer 的评分逻辑不变 |
| 组别对 agent 不可见 | 组别只体现在 prompt 的那一句差异上。run 标签（包含组别）和 run 目录都不能出现在 agent 可见的内容里，这一项由 scorer 的上下文泄露不变量逐个 run 检查：CLI init 事件报告的上下文中，不得出现 run 标签、`runs/agent_verify` 路径或 `_control`/`_treatment` 字样；所有工具返回结果中，不得出现 run 标签或 `runs/agent_verify` 路径。组别字样不在工具返回结果里检查，因为那里是源码，Caddy 仓库中就有 1 行含 `_control` 的代码，会造成误报。v1.1 的 240 个 run 事后按同样标准检查过，没有发现 |
| control 组 | `experiments/agent_verify/prompt.md`，即 v1.1 的原 prompt |
| treatment 组 | `experiments/agent_verify/prompt_path.md`。与 control 的唯一差别是在第 3 步末尾加了一句：「When a conclusion depends on a check, an overwrite, a transformation or any other behavior actually being executed, cite not only that behavior but also every key link on the way from the entry point to it. Keep quotes short, but short does not mean leaving out a link the conclusion depends on.」这句话不涉及任何 fixture、hypothesis、golden 或门槛的信息 |
| 设计 | 8 个 hypothesis × {forward, swapped} × 5 次 × 2 组 = 160 个 run，全部是新的 run |
| 执行顺序 | `experiments/agent_verify/v2_order.txt`，由 `ab.py order --seed 20260927` 生成。一个配对（block）= hypothesis × 条件 × 重复编号，包含 control 和 treatment 各一个 run，两者的先后由种子随机决定。block 按重复编号优先排列。runner 用 `--order` 按文件顺序**逐个 block 执行**：同一个 block 的两个组别同时启动，两边都结束之后才开始下一个 block（`run_in_blocks`），所以每个 treatment 都有一个在时间上紧挨着的 control。组别先后由种子决定（treatment 先 44 次，control 先 36 次），这是固定种子下的随机结果，不做事后调整 |

### 8.2 有效性与重跑

沿用 §1.2 的有效性判定和重跑规则。**只有两个 run 的有效性都严格等于 `VALID` 的配对才进入分析**。如果重跑之后仍有一方无效、被预算守卫拦下，或者根本没有跑，整个配对从两组中一起剔除，并在报告里列出。应有哪些配对，以 `v2_order.txt` 为准，而不是以实际跑了哪些为准。

**样本下限**：每个「hypothesis × 条件」单元的 5 个 block 里，至少要有 4 个完整的 VALID 配对。任何一个单元达不到，v2 对主要问题的判定就记为 `INCONCLUSIVE_INFRA`，既不算成功也不算失败。`ab.py compare` 会输出每个单元的有效配对数。

### 8.3 预算

沿用 §3.6 的启动上限规则和花费定义。v2 的名义上限是 **$150**，两组共用；单次预留 $3。按 v1.1 观察到的单次最高花费（$0.68）推算，160 个首轮尝试约 $109（平均 $0.35 时约 $56）。这不是严格意义上的最坏情况：重跑和单次预留都会增加花费。真正起控制作用的是 $150 的启动上限，所以不设裁剪规则，也不设 gate。

### 8.4 主要结果与成功条件

主要指标是配对样本上的「证据完整且归因正确率」，定义与 §4 相同，golden 不变。由 `ab.py compare` 计算，**三条同时成立才算成功**：

1. treatment 的证据完整且归因正确率 ≥ 60%；
2. treatment 减 control 的这项指标 ≥ 20 个百分点；
3. treatment 的归因正确率 ≥ 80%，且比 control 低不超过 10 个百分点。

**最终判定**（`ab.py compare` 的 `verdict` 字段）按下面的优先顺序确定：

1. 任何单元低于样本下限 → `INCONCLUSIVE_INFRA`；
2. 否则，任一组的 harness 不变量（§2.1 的各项为 0，INFRA_INVALID 占比 ≤ 5%）不满足 → `HARNESS_INVALID`：先修 harness，不给出成功或失败的结论；
3. 否则，三条都成立 → `SUCCESS`，有任何一条不成立 → `FAIL`。

`experiment_success` 只有在 `SUCCESS` 时才为真。只看统计门槛的结果单独记在 `metric_success` 字段里。判定依据是上面的预注册门槛，不依赖事后的 p 值：同一个 hypothesis 的多次重复之间存在聚类，不能当作独立样本。

### 8.5 报告项（不作为判定条件）

- **Caddy 单独报告**：它在 v1.1 里路径事实的引用率是 0%，是检验这个机制最强的 fixture。
- 每组的路径事实引用率和翻转事实引用率。
- 按 fixture、按 hypothesis 的证据完整率。
- 分数先冻结（§1.4），再看 transcript。

### 8.6 结果的解释（事先约定）

| 结果 | 解释 |
|---|---|
| 三条都成立 | 瓶颈主要在证据如何引出（引用协议），而不是安全归因能力本身 |
| 两组都 ≥ 60% | 明确要求路径不是必要条件，**不能**说 treatment 解决了问题；同时说明 v1.1 的 25% 不稳定 |
| treatment 提升很大，但归因条件不满足 | 只是诱导 agent 多引用，不算成功 |
| treatment < 60% | 光靠 prompt 不够，进入 v3：新增结构化的 `path_evidence` 字段，只改这一个变量 |

在任何情况下，都不能因为 treatment 引用了运行时代码而不是挂载代码，就回头修改 golden。

## 9. Spike P：provider 能否提供可达性证据（定向查询）

**背景**：v1.1 和 v2 都已冻结为失败实验。agent 能把翻转点引用得很好（引用率 95–98%），但一直引用不全路径。按 B 方案，可达性证据应当由结构化 provider 来提供，agent 只负责判断安全语义。本 spike 回答一个问题：**只给定两个端点，provider 能否在不借助任何 fixture 特有中间信息的情况下，自己恢复 golden 里的路径事实？**

**不回答的问题**：发现能力。入口和翻转点都是事先给定的，golden 也是人读代码后写出来的。即使完全恢复，也只能说明「在端点已知的定向查询里，provider 能恢复这些类型的连接」，说明不了它能在陌生的 diff 里自己找到入口、sink 和路径；后者属于 1A。本 spike 不调用任何 LLM。

### 9.1 provider 与版本

| provider | 版本与取得方式 | 定位 |
|---|---|---|
| Trailmark | `trailmark==0.5.0`，用 `uvx` 临时运行 | 调用图基线 |
| CodeQL | `codeql-bundle-v2.27.1`（linux64，sha256 `1d380f79…c6b815`），项目本地安装，只在 §9 冻结之后下载 | 数据流 |

- **CodeQL 授权**：依据 https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md （2026-09-28 阅读），明确允许用于学术研究和分析 OSI 许可的开源代码。三个 fixture 分别是 BSD-3-Clause（Authlib）和 Apache-2.0（Caddy、File Browser），在允许范围内。**这不代表将来产品化使用也被允许**，那需要另行审查。
- Go 的数据库构建使用 §3.5 的工具链（Go 1.26.8，`-mod=readonly`）。Caddy 按 §3.5 的最小宿主规则，只构建 `./modules/caddyhttp/reverseproxy/forwardauth/`，两侧命令相同；File Browser 构建 `./http/`；Python 不需要构建。

### 9.2 输入与防止循环论证的规则

1. **provider 只拿到端点**（`experiments/provider_reach/endpoints.yaml`）。端点只能取以下三种之一：case.yaml 的 hint 入口（v1.1 之前冻结）、golden 的翻转点、入口函数自身对外的输出（返回值，或交给下游的参数）。**golden 的中间位置不能作为端点**，有测试检查这一点。
2. 查询里不能出现 fixture 特有的中间符号、文件名或行号。**每种语言只有一个通用查询**（`queries/{python,go}/ReachTaint.ql`，path-problem 类型）。三个 fixture 共用这个查询，只替换生成的 `Endpoints.qll`。
3. **只使用标准库默认的数据流和 taint step**，不添加 `isAdditionalFlowStep`、自定义 barrier 或框架模型。
4. **Trailmark 不能手写 `links.toml` 之类的补边。**
5. 查询和评分代码在冻结后不再修改（例外见 §9.5）。只有评分器会读 golden。

### 9.3 关系类型与表达能力（运行前判定）

必需的路径事实是各 golden 中的 `*-decode-reaches-verify`、`*-copy-routes-run-on-2xx`、`*-stored-path-becomes-entry`，两侧都要求。每个位置的关系类型如下：

| fixture | 位置 | 关系类型 |
|---|---|---|
| Authlib | `jwt.py:104`（`self._jws.deserialize_compact(...)`） | `call_typed_attribute` |
| Authlib | `jws.py:106-109`（从注册表选出算法 → `algorithm.verify`），**anchor 为 106 和 107** | `registry_dispatch` |
| Caddy | base 180 / head 182（`StatusCode: []int{2}`） | `guard_property` |
| Caddy | base 198, 215 / head 233, 240（`Routes`、`HandleResponse` 的 append） | `object_composition` |
| File Browser | 125（`path` → `nameInArchive`）、base 131 / head 137（`NameInArchive:`） | `field_flow` |

**表达能力**是按 provider 的输出格式事先判定的。Trailmark 的输出格式只在 synthetic-notes 上观察过：函数节点带行范围，`calls` 边没有调用点的行号，实例方法调用会变成 `proxy.unresolved`。

| 关系 | Trailmark 0.5.0 | CodeQL 冻结的 taint 路径查询 |
|---|---|---|
| call_typed_attribute | ✗（只有函数粒度） | 由 pilot 校准 |
| registry_dispatch | ✗ | 由 pilot 校准（键控选择本质上是控制关系，不是值的派生，默认 taint 模型未必能表示） |
| guard_property | ✗ | **✗**（它是流经对象的兄弟字段，本身不在数据流上） |
| object_composition | ✗ | 由 pilot 校准 |
| field_flow | ✗ | 由 pilot 校准 |

标为「由 pilot 校准」的关系，不能仅凭 CodeQL 在语言层面「能写出来」就判定为可表达。必须由 §9.5 的非评估校准 pilot，在**查询完全不改**的条件下实际确认。报告里称之为「**在冻结查询下、经合成 pilot 校准的表达能力**」。某项校准结果为 false，只说明这个基线查询在操作层面有边界，**不说明** CodeQL 这门语言在理论上表达不了这种关系。

恢复情况（recovery）不事先填写。

### 9.4 评分

- **粒度规则**：只有数据流节点，或语句、表达式级别的证据，才能覆盖 golden 的某一行。函数、类、模块节点即使行范围包含该行，也不算覆盖。proxy 或 unresolved 的边不算恢复。
- **端点解析失败属于流程故障**：评估运行时，只要有一侧端点没有解析到任何数据流节点（`ResolveEndpoints.ql` 的计数为 0），这次运行就记为 `endpoint_failure`，和工具故障同样处理（最终归入 INCONCLUSIVE_TOOL_FAILURE），**不能**算作「可表达但没恢复」。和 pilot 用的是同一个定义。
- **每个位置的分类**：
  - `SUPPORTED_AND_RECOVERED`：可表达，且被证据覆盖；
  - `EXPRESSIBLE_NOT_RECOVERED`：可表达，但没被覆盖；
  - `NOT_EXPRESSIBLE`：按 §9.3 表达不了；
  - `HIT_BUT_NOT_EXPRESSIBLE`：按 §9.3 表达不了，但证据碰巧覆盖了。照样报告，但不计入判定；
  - `TOOL_FAILURE`：数据库构建或查询失败。
- **anchor**：如果一个位置事先指定了 anchor（Authlib 的 106–109 指定了 106 选择算法、107 派发调用），那么只有所有 anchor 都落在同一条路径上，这个位置才算被覆盖。仅仅碰到范围内的某一行（例如只经过 109）不算。
- **relation instance**：同一个 fixture、同一侧、同一种关系的所有位置，必须被**同一条** provider 路径全部覆盖，才算恢复。例如 Caddy 的两处 `object_composition`，如果分别出现在两条不同的路径上，不能拼在一起算恢复。
- **每个事实**：只有当同一条路径覆盖了该事实的全部位置，而且这些位置全部可表达时，才算恢复。
- **这里测的是什么**：本 spike 测的是「provider 从 source 到 sink 的证据路径，是否覆盖了该关系类型所要求的证据位置」，**不是**「provider 明确表示出了这种语义关系」。报告时按这个措辞表述。
- Trailmark 在函数粒度上找到的路径（`function_path_found`）作为参考单独报告。
- 实现：`experiments/provider_reach/reach.py score`，输出 `results/spike-p-reach.json`。

### 9.5 pilot（只用非评估代码）

pilot 只使用非评估代码，规格在 `pilot.yaml`。代码包括 synthetic-notes，以及两个合成模块：`fixtures/_pilot/build_pyregistry.py`（直接调用、在 `__init__` 中确定类型的属性调用、按输入中的键从注册表选择）和 `fixtures/_pilot/build_goflow.py`（field flow、对象组合、跨函数的直接调用）。这两个模块和评估 fixture 没有共用任何代码。

**CodeQL 每对端点有一个角色**：
- 预期行和端点所在的行，在 `pilot.yaml` 里都写明了该行应当包含的代码片段，由测试核对它们与生成的源码一致，以防合成模块被修改后行号漂移。
- `plumbing`（`pilot-py-direct`、`pilot-go-call`）：两个端点都要解析到节点（由 `ResolveEndpoints.ql` 确认），并且要有一条行级路径经过全部预期行。
- `calibration`（`pilot-py-attribute` → call_typed_attribute，`pilot-py-registry` → registry_dispatch，`pilot-go-fieldflow` → field_flow，`pilot-go-composition` → object_composition）：两个端点都要解析到节点。**同一条行级路径是否覆盖全部预期行，决定对应关系的表达能力**（覆盖为 true，否则为 false）。registry 那一对的预期行是注册表选择（29）和派发调用（30）。这里找不到路径是能力方面的答案，不算流程故障。
- `info`（synthetic-notes）：两个端点都要解析，路径情况只做报告。

**Trailmark**（只有函数粒度）：状态为 ok，两个端点函数都能解析出来。标记了 `trailmark_must_find_path` 的几对（`pilot-py-direct` 和三组 Go），还必须找到函数级路径。

**顺序固定**：
1. 第一次冻结（§9 与代码）；
2. 下载 CodeQL；
3. 跑 pilot。流程故障只能修流程层面的东西，改动记入变更记录，然后重跑；
4. 把校准结果 `results/spike-p-calibration.json` 与第二次冻结一起提交；
5. 运行评估 fixture（每个 provider 一次，结果是确定性的）。

校准之后，**只能改变表达能力表的取值**（评分器会读取校准文件）。查询、端点和评分规则都不能改。每次 CodeQL 运行都会先重建工作目录（pack、数据库、SARIF），所以修复后可以安全重跑。**pilot 期间只能修改流程层面的东西**（查询语法、API 名称、端点的名称匹配、SARIF 解析），不能添加 flow step 或任何针对某种关系的逻辑。所有修改都记入变更记录，重新提交冻结之后，才运行评估 fixture。每个 provider 的评估运行各一次（结果是确定性的）。

### 9.6 决策规则（按关系类型判定）

对每种关系类型，只要有任何一个 provider 在全部 fixture、两侧的所有对应位置上都是 `SUPPORTED_AND_RECOVERED`，就判为 **RECOVERED**。

每种关系类型的状态，只根据事先判定能表达它的 provider 来决定（依据 §9.3 的表，不从结果反推）：
- **RECOVERED**：至少有一个这样的 provider，在全部对应的 relation instance 上都恢复了；
- **NOT_EXPRESSIBLE_BY_ANY**：没有任何 provider 能表达；
- **INCONCLUSIVE_TOOL_FAILURE**：没有 provider 恢复，而且其中有 provider 出现了工具故障（没跑出结果，不能当作能力不足）；
- **EXPRESSIBLE_NOT_RECOVERED**：其余情况。

| 结果（按优先顺序） | 决定 |
|---|---|
| 有任何关系是 EXPRESSIBLE_NOT_RECOVERED | `B_GAPS_RECORDED`：在 provider 扩展、v3（agent 自行提交 `path_evidence`，由 runtime 逐条核验）、缩小 B 的范围这三者之间做决定 |
| 否则，有 INCONCLUSIVE_TOOL_FAILURE | `INCONCLUSIVE_TOOL_FAILURE`：修好工具后重跑，不下结论 |
| 否则，有 NOT_EXPRESSIBLE_BY_ANY（事先预计至少有 `guard_property`） | `B_LIMITED_SCOPE_TO_1A`：**这不代表 Spike P 通过了 B 的完整验收**。含义是：在所有事先判定可表达的关系上，没有出现恢复失败，但仍然存在事先登记的 provider 盲区。因此 B 只在已支持的关系范围内进入 1A；已知盲区继续保留，后续报告不能把它算作 provider 已覆盖 |
| 所有关系类型都是 RECOVERED | `B_PROCEEDS_TO_1A` |

**不在本 spike 范围内**：为了让 `guard_property` 变得可表达而加一个通用的「路径上对象的属性」查询。这个需求是 Caddy 的 golden 暴露出来的，放进这次的基线，会把基线测量和针对当前 fixture 的 provider 工程混在一起。如果基线跑完后唯一剩下的缺口是 `guard_property`，就另行预注册一个 **Spike P-extension**：用合成的 guard pilot 加上同一个通用属性查询，单独评估这项扩展。

**注意**：如果按「某个 provider 恢复了所有事实」来判定，由于 `guard_property` 事先就判定为表达不了，结论在运行之前就已经确定了。所以改为按关系类型判定。「每个 provider 各恢复了哪些事实」仍然照常报告。

### 9.7 局限

- 真实的 Caddy 请求路径，要先把配置序列化成 JSON，再按字符串名从模块注册表加载。golden 只覆盖解析阶段、函数内部的组合，所以本 spike 测不到请求时的完整路径。像 Caddy、Django 中间件、Spring bean 这类由配置或注册表驱动的框架，可能需要框架模型。
- 只有 3 个 fixture，关系类型各不相同，结论只能按关系类型来读。

## 10. P-Hybrid-1：provider 逐跳核验（不调用 LLM）

**背景**：Spike P 的结论是 `B_GAPS_RECORDED`，并且暴露了一个测量问题：以端到端路径为单位测，同一条链上一个关系断了，前后已经解析成功的跳也会一起被判为未恢复（`results/spike-p.md`）。与 Codex 讨论后选择混合路线：由 agent 提出逐跳的路径，由 provider 逐跳核验，核验不了的跳明确标为盲区。P-Hybrid-1 先回答这条路线的前提：**给定冻结的单跳（从 golden 位置切出的真跳，加上事先生成的假跳），按关系类型编写的通用核验器，能否安全地核验它们（假跳从不判为 VERIFIED），又能覆盖多少真跳？**

**不回答的问题**：agent 会不会、能不能按这种格式提出跳（那是 P-Hybrid-2 的问题）；发现能力；三个 fixture 以外的普遍性。本阶段不调用任何 LLM。

### 10.1 跳的格式

```
{ id, fixture, revision, relation,
  from: { file, start_line, end_line, expression },
  to:   { file, start_line, end_line, expression } }
```

- 跳文件（`experiments/hop_verify/sets/*.yaml`）只允许这些键。真值标签、变异类型、预期状态和假的理由只写在 `truth/*.yaml` 里，只有评分器读取。`run` 不读 truth。cal 和 eval 的 id 是不透明的（`c01…`、`e01…`），顺序用固定种子打乱，不从 id 或位置泄露真值。
- **expression 的定位**：在 span 内，把连续空白（包括换行）视为一个空格来比较，expression 必须恰好出现一次；定位结果是它第一个字符的行和列（Go 按字节计列，Python 按字符计列，与 CodeQL 的抽取器一致）。定位失败就是 `ANCHOR_REJECTED`，相当于 runtime 的引用检查，在核验器之前发生。
- 端点有两种角色：`node` 指一个节点，节点的起点必须恰好是 expression 的起点；`inside` 指一个位置，这个位置必须落在关系解析出的函数之内（调用类关系的 `to`）。

### 10.2 关系、真值条件与核验器（`relations.yaml`）

关系类型和一句话说明沿用 Spike P 冻结的定义。这里为每种关系补上**真值条件**（用来给跳打标签）、端点允许的节点种类，以及唯一的单跳核验器。

| 关系 | 真值条件（简写） | from / to | 核验器 |
|---|---|---|---|
| call_typed_attribute | `from` 是 `a.b.m(...)`，运行时能调用包含 `to` 的函数 | 属性上的方法调用 / 函数体内 | 标准调用图 `resolveCall`，不改 |
| registry_dispatch | `from` 是 `r.m(...)`，运行时能调用包含 `to` 的方法（注册表是核验器必须跟踪的机制，不是额外的真值条件） | 方法调用 / 方法体内 | 实例的值流（标准 step）+ 一个通用注册表模型 + 方法解析顺序 |
| field_flow | `from` 定义局部变量，`to` 是带键的结构体字面量字段 `f: e` 或字段写入 `x.f = e`，`from` 定义的值在函数内到达 `e`（经过局部变量，以及由它派生结果的调用） | 定义 / 带键字段、字段写入 | 局部 taint，只用标准 step |
| object_composition | `from` 定义一个对象（`v := e`）或通过其变量修改它（`v.f = e`）；`to` 是字段写入 `x.g = e'`。该对象经局部值流就是 `to` 写入的值之一（`append(x.g, ...)` 看追加的参数），或者是其中的直接组成部分（字面量元素、带键的值、`&` 的操作数、调用参数）。**只算一步组合**：只经由更早的写入才到达的对象不算，容器 `x` 本身也不算被写入 | 定义、字段写入 / 字段写入 | 局部值流 + 同一 SSA 版本 |
| guard_property | `from` 是某个带键字段，位于初始化局部变量 `v` 的字面量内部（可经字面量元素、带键的值、`&` 嵌套）；`to` 是读取 `v` 同一个定义的字段写入 `v.f = e` | 带键字段 / 字段写入 | 字面量结构 + 同一 SSA 版本 |

原则：

1. **核验器按关系类型通用**，不能出现 Authlib、Caddy、File Browser 的符号、文件名或行号（有测试检查）。使用与 Spike P 相同的 CodeQL 2.27.1 bundle。每个核验器输出数据库中该关系的全部实例，由 `verify.py` 按端点匹配。
2. **registry_dispatch 的注册表模型**（在开发集上加入，见 10.3）：以模块级变量或类属性命名的容器视为一个抽象位置（类属性经 `cls`、`self` 或类引用解析到定义该属性的类）。写入包括 `c[k] = v`、`append`、`add`、`insert`、`setdefault` 和字面量初始化；读取包括 `c[k]`、`get`、`pop`。用运行时 key 读取可以得到任何一个元素；用字面量 key 读取，只能得到以相同字面量或运行时 key 写入的元素。实例属性、作为参数传递的容器、按字符串动态导入等，不在模型之内（结果为 UNVERIFIED）。
3. **CONTRADICTED 只来自形状检查**：端点在所声称的 revision 的语法树里没有指向允许种类的节点。这是对一个具体文件、一个具体 span 的封闭且完整的搜索。关系本身的检查依赖数据流、调用或类型解析，只能给出 VERIFIED 或 UNVERIFIED。**假跳得到 UNVERIFIED 是正确的安全行为。**
4. 数据库或查询失败、文件没有被抽取，记为 `TOOL_FAILURE`，绝不算作 CONTRADICTED。

### 10.3 三个集合

| 集合 | 代码 | 跳 | 用途 |
|---|---|---|---|
| dev | `fixtures/_hopdev`（Go、Python 各一个模块，base/head） | 35 | 开发核验器。结果（`results/p-hybrid-1-dev.json`）只作参考 |
| cal | `fixtures/_hopcal`（与 dev 和评估 fixture 都不共用代码） | 40 | **执行留出**的校准/挑战集：由同一作者编写（知道核验器的设计，并在加入注册表模型后追加了对抗用例），冻结前没有任何核验器在它上面运行过，冻结后运行一次。它不是独立的未知测试集 |
| eval | Authlib、Caddy、File Browser | 62（真 10，假 52，其中 6 个预计被引用检查拦下） | 评估 |

合成模块的 head 只替换若干行、不移动其他行，这样把一个跳复制到另一个 revision 时，文字保持不变，而它声称的关系可能改变（「错误 revision」变异在合成代码上因此有意义）。

**披露**：
- 核验器只在 dev 上开发。dev 的第一轮中，只用标准 step 的 registry 核验器一个真跳都没有核验到。断点与 Spike P 相同：标准内容模型对 key 敏感（`{"a": X}` 按字面 key 存，`d[kind]` 只读「任意 key」的内容），并且没有跨别名的容器同一性。于是加入了第 2 条的通用注册表模型。
- 加入这个模型之后、cal 第一次运行之前，给 cal 追加了一个对抗性用例：两个类各有一个同名的类属性注册表，只在其中一个注册的实例，不能被判为能从另一个读取。
- golden 和核验器由同一个作者编写，编写核验器和合成模块时已经知道评估代码。防护措施是：核验器必须通用（有测试检查）；cal 留出、冻结前不运行；eval 的跳和变异在任何核验器接触 eval 之前按规则写好，并与核验器一同冻结；节点种类靠人读代码识别，不在 eval 上运行形状查询。

**真跳的切分规则**：对每个路径事实（各 revision 分别处理），链 = 该证据集的位置按列出的顺序排列；如果 Spike P 的 sink 端点本身也是同一 hypothesis 的 golden 位置，就把它接在链尾（只有 Authlib 的 `jws_algs.py:37-38` 满足）。链上相邻的两个位置构成一跳，关系取第一个位置在 Spike P 中的标签（`endpoints.yaml`），最后一个位置不再起跳。不引入 golden 以外的位置（例如 Caddy 运行时的 `reverseproxy.go`）。

| fixture | 每个 revision 的真跳 |
|---|---|
| Authlib（两侧代码相同） | `jwt.py:104` → `jws.py:106-109`（call_typed_attribute）；`jws.py:106-109` 中的 `algorithm.verify(...)` → `jws_algs.py:37-38`（registry_dispatch） |
| Caddy | base 180 → 198、head 182 → 233（guard_property）；base 198 → 215、head 233 → 240（object_composition） |
| File Browser | 125 → base 131 / head 137（field_flow） |

每种关系各 2 个真跳（base、head 各一个）。有测试直接从 golden.yaml 和 endpoints.yaml 按上述规则重建链，要求 eval 的真跳与重建出的相邻位置对（含关系标签）**完全一致**，从而排除把两个无关事实的位置拼成一跳的情况。

### 10.4 假跳（变异）

对每个真跳，按以下规则生成全部候选：

1. **reversed**：交换 from 和 to。
2. **wrong_revision**：换到另一个 revision，span 和 expression 都不变。被引用检查拦下的，记为 `caught_by_anchor`（这不算核验器的用例，但会报告出来）；与另一侧的真跳完全相同的，作为重复项删除（Authlib 的 4 个，记在 `dropped_before_freeze`）。
3. **shift**：把 from 移到同一文件、同一 revision 中最近的、允许种类的节点上，从真跳 from 的起始行分别向上和向下找（不包括真跳的 to），expression 取新位置上真实的代码。
4. **wrong_target**：用同样的方法移动 to（`node` 角色，排除真跳的 from）。`inside` 角色（调用类关系）的候选，则是同一 revision 中与被调方法同名的其他函数。

在搜索过程中，按真值条件实际为真的候选跳过、记为 `skipped_true`，继续向外找（例如 Caddy 中同一个 `goodResponseHandler` 字面量里的其他字段，以及 Authlib 中其他已注册算法的 `verify`）。每个假跳都写明为什么是假的，在冻结前由人工确认。按（fixture, revision, relation, from, to）去重。**运行之后不能删除任何负例**；冻结前唯一的删除，是上面记录的重复项。

### 10.5 状态、指标与分类

- 状态：`VERIFIED`、`UNVERIFIED`、`CONTRADICTED`、`ANCHOR_REJECTED`（引用检查拦下，不送入核验器）、`TOOL_FAILURE`。
- 每种关系在每个集合上的指标：
  - `false_verification_rate`：被判为 VERIFIED 的假跳 ÷ 送入核验器的假跳，必须为 0；
  - `true_hop_coverage`：被判为 VERIFIED 的真跳 ÷ 真跳；
  - `verification_precision`：VERIFIED 中真跳所占的比例；
  - 另外报告 `true_contradicted`（被判为 CONTRADICTED 的真跳）、`caught_by_anchor`，以及按变异类型分列的状态。
- 分类（按优先顺序）：
  - **UNSAFE**：有假跳被判为 VERIFIED，**或者有真跳被判为 CONTRADICTED**（后一条是在 Codex 的定义之上补充的：一个会驳回真实证据的核验器，和一个会接受假证据的核验器一样不能用）；
  - **INCONCLUSIVE_TOOL_FAILURE**；
  - **SUPPORTED**：全部真跳都被判为 VERIFIED；
  - **PARTIAL**：部分真跳被判为 VERIFIED；
  - **BLIND**：没有一个真跳被判为 VERIFIED。
- 实现：`experiments/hop_verify/verify.py score`，输出 `results/p-hybrid-1-{cal,eval}.json`；provenance 包含核验器、集合文件和 scorer 所读 truth 文件的 sha256。

### 10.6 判定与路由（`verify.py decide`）

| 结果（按优先顺序） | 决定 |
|---|---|
| 任何关系在 cal 或 eval 上是 UNSAFE | `NO_HYBRID_2`：不进入 Hybrid-2 |
| 否则，四个 Spike P 缺口（registry_dispatch、field_flow、object_composition、guard_property）中至少有一个**合格** | `HYBRID_2_LIMITED_SCOPE`：Hybrid-2 只针对合格的关系；其余关系声明为盲区（provider 只会说 UNVERIFIED，产品上显示为「未核验」） |
| 否则，有缺口关系在 cal 或 eval 上是 INCONCLUSIVE_TOOL_FAILURE（或缺少 cal 结果） | `INCONCLUSIVE_TOOL_FAILURE`：只修复流程层面的问题后重跑（最多 3 次） |
| 其余情况 | `NO_NEW_CAPABILITY`：P-Hybrid-1 没有带来新的核验能力 |

**合格**的关系必须同时满足：在 eval 上是 SUPPORTED 或 PARTIAL；cal 结果存在，且不是 INCONCLUSIVE_TOOL_FAILURE（cal 和 eval 都不是 UNSAFE 已由第一行保证）。也就是说，留出校准没有正常完成的关系，不能凭 eval 的覆盖进入 Hybrid-2；但它也不会阻塞其他已正常核验的关系。

`HYBRID_2_LIMITED_SCOPE` **只说明**：对这些关系，冻结的通用核验器能安全地核验这些 golden 位置上的单跳。它**不说明** agent 会提出这样的跳，也不说明在其他代码上的覆盖率。

### 10.7 顺序

1. 冻结（Codex 审查之后提交）：§10、`relations.yaml`、查询、`verify.py`、三个集合和各自的 truth、dev 结果、预测（`results/p-hybrid-1-predictions.md`）；
2. 运行 cal 一次，得出分数后提交；
3. 运行 eval 一次，得出分数后提交，再运行 `decide` 并提交；
4. 写报告。

核验是确定性的，所以每个集合只运行一次。工具故障只能在流程层面修复后重跑，并记入变更记录。冻结之后，如果要修改核验器、跳或 truth，就是新的协议版本，需要新的 cal 集；旧版本的 eval 结果保留，不能覆盖。

### 10.8 局限

- 每种关系只有 2 个真跳，结果只能读作「在这些位置上可行」，不能当作覆盖率的估计；base/head 的两个真跳本身高度相关。
- eval 的负例是从冻结的真跳系统变异出来的相关挑战用例，不是从真实的假跳总体中随机抽样的。因此 `false_verification_rate` 和 `verification_precision` 只描述本集合（「在这套预注册的变异挑战上没有观察到误核验」），不能用来估计总体误报率。
- CONTRADICTED 只来自形状检查，没有尝试语义层面的反驳。
- 假跳的真值靠人工确认；规则是确定性的，但节点种类是人读代码识别的。
- 注册表模型把同名的容器合并成一个位置，不区分 key。它对注册表语义（任何已注册的项都可能被运行时数据选中）是保守的，但用常量索引读列表时会高估。

## 11. P-Hybrid-2：agent 提出带类型的跳，核验反馈的配对 A/B

**背景**：P-Hybrid-1 的结论是 `HYBRID_2_LIMITED_SCOPE`。对五种关系，冻结的通用核验器能安全地判断单跳。问题于是转到 agent 一侧。本实验同时回答两个问题：
- **提案能力**：在收到任何核验反馈之前，agent 能否提出与冻结 golden 一致、并能被核验的带类型的跳？
- **反馈效果**：看到 `VERIFIED` / `UNVERIFIED` 之后，agent 修订出的结果，是否好于同一份初稿、在没有反馈的条件下修订出的结果？

**不回答的问题**：归因（本实验不要求 agent 给出结论）、发现能力、三个 fixture 以外的普遍性。

### 11.1 设计

- **单位是 block**，即（fixture, repeat）。三个评估 fixture 各取 H1，每个重复 5 次，共 15 个 block。顺序由固定种子 20260929 生成，按重复轮次排列、轮内打乱（`order.txt`）。
- **每个 block 的流程**：
  1. 父会话（initial 阶段）提出并锁定初始跳；
  2. 把锁定后的状态复制成不可变的快照，并记录 sha256；
  3. 两个分支同时用 `claude -p --resume <父会话> --fork-session` 从同一个父会话分叉出来，分别是 control 和 treatment；
  4. 每个分支修订一次，最终提交一次。
- 两个分支拿到的初稿完全相同，所以 **pre-feedback recall 由两组共享**，反馈增益就是同一份初稿上的配对差 post_T − post_C。
- **不设自动回退**：分叉机制已在冻结前的 plumbing pilot 上验证（§11.8）。冻结后如果分叉失败，记为 `INCONCLUSIVE_INFRA`，不能在运行中改成两组各自独立的设计，因为那会改变估计量和噪声结构。
- **模型与 CLI**：与 v2 相同，`claude-sonnet-5`、effort `high`、Claude Code 2.1.280；每个进程 `--max-budget-usd 3`，超时 1200 秒。全部是新 run，不复用 v1.1 或 v2 的 transcript。
- **评估运行只能从冻结的 commit 开始**：工作树不干净时，runner 拒绝启动，并在每个 meta 中记录 harness commit。
- **有效性与重跑**沿用 §1.2：只有 INFRA_INVALID 可以重跑，最多 3 次。父会话失败时整个 block 从头重跑；子会话失败时，从同一个父会话重新分叉。遇到额度耗尽，整批停止，恢复后再继续。

### 11.2 agent 的接口（`src/spike/hop_session.py`、`hop_mcp_server.py`）

- **工具**：
  - 与 v1.1 相同的读取工具（`list_files`、`read_code`、`search_code`、`find_symbol`、`changed_files`、`diff_file`、`map_location`）；
  - `get_task`；
  - `validate_hop`；
  - `submit_hops`。
  - 没有 `submit_observation`，也没有 `finish`。
- **`get_task` 的内容**：H1 的 claim、components、hints，跳的格式（与 §10.1 的 schema 完全相同），关系词表（`vocabulary.yaml`：五种关系冻结的一句话说明及其真值条件的复述，外加 `unsupported`），节点种类的说明，以及当前阶段的规则。
- **`validate_hop`**：两组在整个过程中都可以用。它只检查 schema、anchor（expression 在 span 内恰好出现一次）和节点种类（即 §10 的形状检查），**从不判断关系本身是否成立**。
- **`submit_hops`**：
  - 去重之后最多 12 个跳（initial 和 final 使用同一个上限）；
  - 只要有一个跳没通过校验，就整批不锁定；
  - 每个阶段只能成功提交一次，之后的提交一律拒绝；
  - 因此锁定的跳里**不可能出现 CONTRADICTED 或 ANCHOR_REJECTED**。形状安全已由接口在构造上保证，所以 contradiction 不作为成功条件，而是一条 harness 不变量（§11.7）；本实验在经验层面的安全防线是盲审的 FALSE share。
- **`unsupported` 关系**：只检查 anchor，永远是 UNVERIFIED，不计入 golden 覆盖，单独统计数量和比例，并进入盲审。报告两组的 `unsupported` 使用量相对初稿的变化，以识别「把坏跳改标成 unsupported」的情况。
- **修订消息**：
  - control 收到 `revision.md`；
  - treatment 收到的是 **control 的消息加上一段内容**，逐字节相同（`feedback.py`，有测试检查）。这段内容只有标题、每个初始跳一行（id + 状态）和固定图例：VERIFIED 表示「核验器确认了这个跳两端之间的关系」，UNVERIFIED 表示「核验器无法确认；该跳仍可能为真」；
  - 反馈中不出现解析目标、候选、下一跳、golden 信息或核验器内部路径；
  - 初始阶段和 control 分支里从不出现 verifier 一词；
  - 反馈只发生一次，最终提交之后不再有任何核验反馈。

### 11.3 冻结的核验器（`freeze_rows.py`，`frozen/`）

- P-Hybrid-1 的查询、模型和 `relations.yaml` 全部冻结。冻结时，在每个评估 fixture 的每个 revision 上，用冻结的 `hop_verify/verify.py analyze`，把该语言的**全部**关系查询和形状查询各运行一次。结果排序后存为 `frozen/*.json.gz`，并记录 sha256 清单。
- 运行时的校验、treatment 的反馈和评分，都只读这些文件，P-Hybrid-2 期间不运行任何核验器。
- `spike.hops` 复现了 §10 的 `judge`：有测试要求它在全部 62 个 eval 跳上给出与已提交的 P-Hybrid-1 结果相同的状态。
- **看到 Hybrid-2 的输出之后，不得补充任何关系模型。** 新类型的跳只能得到 UNVERIFIED，或以 `unsupported` 提出，并作为将来的盲区记录下来。

### 11.4 golden 与匹配规则

- golden 是 §10 冻结的 10 个真跳（Authlib 4、Caddy 4、File Browser 2），不做任何修改。
- **节点身份由冻结的 resolver 生成**：
  - `node` 角色：anchor 处起始的、允许种类的节点，身份为（文件, 行, 列）；
  - `inside` 角色：包含 anchor 的最内层函数（取自形状行中的 function_body / method_body），身份为这个函数。宽的函数范围不会因此放宽 golden。
- **类型匹配**：revision 相同，关系相同，from 是同一个节点，to 的身份相同。
- **位置匹配**：revision 相同；from 的 anchor 与 golden 的 from 节点起点相同；to 按 golden 关系的角色判断，`node` 角色要求起点相同，`inside` 角色要求在同一个最内层函数之内。不看跳本身标的关系。
- **verified golden-hop coverage（主指标）**：在该 fixture 的 golden 跳中，被某个 VERIFIED 的跳类型匹配到的比例。**located coverage** 是被位置匹配到的比例。报告时把每个 golden 跳分成三类：「没找到位置」「找到位置但没有得到类型匹配的 VERIFIED」「已核验」。

### 11.5 指标

- **pre-feedback recall**：初稿的 verified coverage，两组共享。**post**：各组最终提交的 verified coverage。两者都另报 located coverage。
- **feedback gain**：每对的 post_T − post_C。
- **proposal verification rate**：VERIFIED 的跳 ÷ 全部锁定的跳（按组汇总）。
- **contradiction rate**：CONTRADICTED ÷ 非 unsupported 的跳。按构造为 0，只作报告，不是成功条件。
- **unsupported 数量与比例**：按组报告。
- **novel-hop validity**：盲审结果，TRUE、FALSE、INDETERMINATE 各自的计数。**FALSE share = FALSE ÷ (TRUE + FALSE)**，按出现次数计，统计范围是该组的最终提交；INDETERMINATE 单独报告。
- **Caddy**：每对各自覆盖到的 golden 跳、T > C 的对数，以及「初稿中尚未被核验覆盖、后来只在 treatment 的修订中被覆盖」的 golden 跳。
- **0/0 的约定**（事先确定）：分母为 0 的比率一律记为 0（什么都没有声称）。这适用于没有 novel 跳的组的 FALSE share，也适用于没有非 unsupported 跳的组的 contradiction rate。

### 11.6 盲审（`propose_review.py`）

- **单位**：一个 novel 跳的身份，即（fixture, revision, relation, from 节点, to 节点；unsupported 用 anchor）。在所有提交（初稿和两组的最终提交）中去重，同一个单位的标签适用于它的每一次出现。
- **审阅表**：
  - 用种子 20260930 随机排序；
  - 每个单位只显示仓库名、revision、关系的定义、两个端点以及前后 6 行代码；
  - 不显示 case id、组别、阶段、核验结果、golden 匹配情况或 agent 写的文字；
  - 工具自己生成的文字会做泄露检查。
- **primary reviewer**：一位此前没有参与本项目的人。此人没有看过 golden、核验器或 §11，也没有看过组别和核验结果。因此，转述过审查的用户、本轮之前的 Codex 会话和作者本人，都不能担任。
- **secondary reviewer**：一个全新的 ChatGPT 会话（与被测 agent 不同家族），只给它同一份表和标签说明，不给任何项目历史。只报告它与 primary 的一致率；模型不裁决人的标签，分歧也不改变 primary 的结果。
- **找不到独立的人时**：由模型审阅作为 primary，但报告里必须明确标为 **model-blind adjudication**（较弱的次要证据），不能称为人工 truth。
- **标签文件**提交为 `results/p-hybrid-2-review-{primary,secondary}.yaml`，必须包含 reviewer 块：`type`（human / model）、`name`、`date`，以及 attestation（`independent: true`、`saw_arms: false`、`saw_verdicts: false`）。scorer 检查这些字段是否齐全，以及每个审阅单位是否都有标签；缺任何一项，就视为尚未审阅（`REVIEW_PENDING`）。scorer 无法证明声明属实，只能保证最终产物记录了审阅者是谁、以及声明的盲审条件。

### 11.7 判定（`propose_score.py`，按顺序）

1. **`INCONCLUSIVE_INFRA`**：任一 fixture 的完整配对（父会话和两个子会话都是 VALID）少于 4/5。冻结后的分叉失败也归入这一类。
2. **`HARNESS_INVALID`**：出现以下任一情况：
   - 隔离被破坏：父会话文件发生变化、子会话的快照 hash 与父会话快照不同、子会话恢复出的初稿与快照不同，或者分叉没有得到新的会话；
   - 上下文泄露：cwd 在仓库内、auto-memory 非空，或者组别、block、run 目录出现在 init 事件或工具结果中；
   - 使用了 secreview 以外的工具；
   - 出现 harness 错误；
   - 冻结分析的 hash 对不上；
   - 任何锁定的 initial 或 final 跳在 scorer 中出现 anchor 或形状失败（记为 CONTRADICTED），说明运行时校验与冻结的 scorer 不一致。
3. **`REVIEW_PENDING`**：primary 标签缺失或不完整。
4. **`SUCCESS`** 要求以下条件同时满足，否则为 **`FAIL`**：
   - 配对的平均 post_T − post_C ≥ +15 个百分点；
   - treatment 严格低于 control 的对 ≤ 2 个；
   - treatment 的 FALSE share ≤ control + 10 个百分点；
   - **至少有一个 Caddy 对，treatment 最终的 verified golden coverage 严格高于从同一份初稿分出来的 control。**

**结果的解读**（事先登记，只作描述，不改变判定）：

| 模式 | 解读 |
|---|---|
| 初稿 located coverage 低（< 30%），盲审为 TRUE 的 novel 跳也少 | 在这个接口下，agent 提不出正确的跳 |
| 位置找到了，但 verified coverage 远低于 located coverage | agent 能找到位置，但给不出可核验的形式或关系类型 |
| SUCCESS | 核验反馈能有效纠正 |
| 平均增益的绝对值 < 5 个百分点 | 核验反馈基本不起作用 |

介于这些模式之间的，照实际情况报告。

### 11.8 plumbing pilot（冻结前，只用合成代码）

- 在 `fixtures/_hoppilot`（hopdev 的 Go 和 Python 模块）上用 Haiku 4.5 各跑 1 个 block（`results/p-hybrid-2-pilot.json`）。确认了以下各项：
  - `--resume --fork-session` 可用，两个分支都得到了新的会话，并且都延续了父会话的上下文；
  - MCP 的锁定状态能从快照中恢复；
  - 父会话文件在两个分支运行前后的 sha256 相同；
  - 两个子会话的快照 hash 与父会话一致；
  - auto-memory 为空；
  - 没有上下文泄露，也没有使用外部工具；
  - CLI 的会话文件已随 run 保存，并清理了 per-cwd 的项目目录。
- pilot 不计分。

### 11.9 局限

- **关系词表本身就是提示**：`guard_property`、`object_composition` 是按 Caddy 的 golden 结构命名的。pre-feedback 的提案能力是「在给定这五类关系词表的接口下」的能力，**不能与 v2 自然语言的路径引用率直接比较**。
- 形状校验两组都能用，所以格式修复（换节点）两组都能做。本实验估计的只是**关系层面**核验反馈（VERIFIED / UNVERIFIED）的效果，数值可能偏小。
- 只有 15 对，golden 只有 10 个跳，结论只针对这三个 fixture。
- agent 可能提出 golden 以外、但确实成立的替代跳。主指标不计入它们，它们的有效性由次要指标（盲审）反映。
- pilot 中已经观察到：treatment 会删除 UNVERIFIED 的跳。对于真但不可核验的跳，这会降低 novel TRUE 的数量；主指标不受影响（golden 跳在形式正确时都能被核验）。

### 11.10 顺序

1. §11、代码、冻结分析、pilot 结果 → Codex 审查 → 冻结提交；
2. 按 `order.txt` 运行 15 个 block；
3. `propose_score.py`（此时判定为 `REVIEW_PENDING`）→ 提交分数；
4. `propose_review.py export` → primary 与 secondary 盲审 → 提交标签 → 重新计分，得到最终判定 → 提交 → 写报告。

## 12. 链复现（Chain Replication）：局部可核验证据链的可行性（草案，未冻结）

### 12.0 阶段转换与设计诊断

- **旧的证据契约基准到此结束。** v1.1、v2、Spike P、P-Hybrid-1、P-Hybrid-2 全部保持原判定。P-Hybrid-2 在盲审完成后以 FAIL 关闭（它的 SUCCESS 条件中有两条与盲审无关，已经不成立）。任何旧数据都**不会**用链级标准重新评分。
- **新问题**（与 Codex 讨论确定）：在冻结的局部核验器下，不指明位置的「链完整性」反馈，能否帮助 agent 补全一条从 entry 到 behavior、每一跳都被判为 VERIFIED 的证据链？golden 链继续作为参考和报告，但不再规定唯一合法的中间路径。五类核验器、查询和关系语义全部冻结；不会因为 agent 的输出而扩展关系词表。
- **设计诊断**：在写正式协议之前，用 P-Hybrid-2 已冻结的**初稿**（两组共享；两组的 final 有意不读）做一次不计分的诊断（`experiments/hop_chain/diagnose.py`）。它的规则写在脚本 docstring 中，**在第一次运行之前随本条提交**：
  - 边与节点身份；
  - 连接器 C1（节点身份，以及「函数 → 其中的节点」）；
  - 连接器 C2（C1 加上 Go 的同一对象，启发式）；
  - 端点规则 G（golden 链的首尾节点，guard 跳除外）；
  - 限定规则 Q（golden 含 guard_property 时，要求路径上挂有一个已核验的 guard）；
  - 只算简单路径，最多 12 条边。
  - 诊断结果**只作设计信息**，不是基线，也不用来定门槛。
- **Spike P 端点在五类关系下不可表达**（人工判断）：
  - Authlib 的 source 是参数 `s`，不是任何节点种类；
  - File Browser 的 source 在 `rawDirHandler` 中，要到达 `getFiles` 必须经过一次 Go 函数调用（实参 → 形参），五类关系里没有这种关系；
  - Caddy 的 sink 是 `return`，也不是节点种类。
  - 因此「产品级 entry」只能取 golden 链的起点。这是冻结核验器的盲区，只记录，不补。


**§12.0 诊断之后的决定**（与 Codex 讨论）：
- 不做完整性反馈 A/B：15 对中只有 2 对可能携带信息，而且这 2 对都是同一个起点盲区。
- 先把 C2 正式化成一个经过校准、冻结的「同一对象」连接器（§12.1）。
- 再做一次**全新的、没有反馈的描述性复现**（§12.2）。
- File Browser 从翻转行出发的情况记为 `ENTRY_GAP`（后半段已核验，但起点连接器是盲区），**不算**完整链。
- C1 按节点身份连接，它在产品链判据上**没有通过构念效度检查**：它与 golden 严格匹配完全相同。

### 12.1 同一对象连接器（C2）

- **它是什么**：图层面的节点等价规则，**不是**第六种安全关系。输入两个 resolved 节点，输出只有 `SAME_OBJECT` 或 `NOT_PROVEN_SAME`，从不断言「不同」。它必须证明的是程序中的对象身份，而不是「两段源码看起来在说同一个变量」。
- **实现**（`experiments/hop_chain/queries/go/SameObject.ql`，CodeQL 2.27.1，Go）：
  - **对象节点**有两种：只定义一个局部变量的语句（`v := e`、`v = e`、`var v = e`），以及对普通局部变量的字段写入（`v.f = e`）；
  - 两个对象节点当且仅当对应**同一个显式 SSA 定义**时，判为同一对象；如果一个节点意外对应到多个定义，这个节点就不参与判定；
  - 以下情况都不输出（即 NOT_PROVEN_SAME）：一次定义多个变量；经 phi 合并或闭包捕获的定义；可能被间接引用的变量（取了地址、调用了指针接收者方法、名字解析不完整，即 `mayHaveIndirectReferences`）；嵌套字段写入（基不是普通变量）；
  - 查询里不出现任何 fixture 的名字、文件或行号（有测试检查）；
  - Python 不使用这个连接器，只用 C1（「函数 → 其中的节点」）。
- **校准**：
  - dev（`fixtures/_objdev`，25 对）用于开发，结果只作参考：10/10 个「同一」对判为 SAME_OBJECT，「不同」和「并非总是同一」都没有被判为 SAME_OBJECT，4 个「同一但无法证明」都被保守拒绝；
  - cal（`fixtures/_objcal`，24 对）留出，在冻结前没有运行过，冻结后运行一次。对抗用例包括兄弟块同名、switch 遮蔽、循环 phi、else 分支重新定义、经函数返回的副本、指针别名、嵌套字段、goroutine 捕获、零值 `var`、指针接收者方法。
- **安全判定**：在「不同」或「并非总是同一」的对上判出 SAME_OBJECT，即为 **UNSAFE**。「同一」对的覆盖率和「无法证明」的处理照实报告。
- **cal 是复现的硬性前置条件，没有任何回退。** C1 已经没有通过构念效度检查，因此不能在连接器失败后改用 C1 正式计分（C1 至多作为诊断输出）。以下三处都机械地执行这个条件：
  - **runner**：启动任何评估会话之前，要求 `results/chain-connector-cal.json` 存在，其中记录的查询和 `cal.yaml` 的 hash 与当前文件一致，并且 `unsafe` 为空；四个评估 revision（Caddy、File Browser 的 base / head）的连接器输出齐全，与清单 hash 一致。
  - **`connector.py freeze --targets eval`**：同样要求 cal 已通过。
  - **scorer**：同样检查。不满足时不输出任何链分类：cal 为 UNSAFE，判为 `CONNECTOR_CALIBRATION_FAILED`（停止复现）；其他缺失或不一致，判为 `PROTOCOL_INVALID`。
  - cal 只能运行一次，已有结果时拒绝再跑。
- **连接器安全、但在真实代码上因为保守而什么都证明不了，是可以接受的正式结果**，不能因为覆盖率低而修改连接器。
- **评估 fixture 的连接器输出**只在 cal 通过之后计算，并记录 hash 清单。

### 12.2 描述性复现（没有反馈）

- **问题**：给定关系词表、冻结的局部核验器和冻结的连接器，agent 在没有任何反馈的情况下，一次性提交的跳是否经常已经构成完整的已核验链？这不是 A/B，没有 control，也没有 treatment。
- **会话**：面向 agent 的 prompt、工具接口、模型与 effort，以及初始阶段的执行配置（`get_task`、词表、校验与锁定、会话持久化、`claude-sonnet-5` effort high、$3、1200 秒），都与 P-Hybrid-2 相同，只有新生成的会话和 run 标识不同。全部是新 run。3 个 fixture（各取 H1）× 10 次重复 = 30 个会话；顺序由固定种子 20261001 生成，按重复轮次排列（`order.txt`）。runner 只在工作树干净时启动。
- **端点**：
  - 规则 G（`anchors.yaml`，有测试从冻结 golden 重新推导）：
    - Authlib：entry 是 `jwt.py:104` 的调用，terminal 是 `NoneAlgorithm.verify` 的函数体；
    - Caddy：entry 是 `Routes` 写入（198 / 233），terminal 是 `HandleResponse` 写入（215 / 240），并要求挂一个 guard；
    - File Browser：entry 是 125 的定义，terminal 是 `NameInArchive` 字段（131 / 137）。
  - 端点只在计分时使用，不告诉 agent。
- **图**（`chain.py`）：
  - 边：关系类型受支持、并且被冻结核验器判为 VERIFIED 的锁定跳；
  - 连接：C1，外加（Go）经冻结连接器证明的同一对象；
  - 路径是**节点简单**的：除了一条边与上一条边的衔接点，路径上不重复访问同一个节点，也不重复访问被证明为同一对象的节点。最多 12 条边；
  - 需要 guard 时（Caddy），路径上必须挂有一个已核验的 guard 跳，挂点可以经同一对象成立。
- **分类**：按以下顺序，取第一个成立的：
  - `FULL_CHAIN`：存在一条从 entry 到 terminal 的完整路径（需要 guard 时已挂上 guard）；
  - `QUALIFIER_GAP`：完整路径存在，但缺少所需的 guard；
  - `ENTRY_GAP`：有已核验的路径到达 terminal，但不从 entry 出发。报告**最长的已核验后半段**的边数（`longest_suffix_edges`；取最短的话，几乎总是最后一跳），以及是否挂有 guard；
  - `INTERNAL_GAP`：有已核验的边，但没有任何路径到达 terminal。报告是否存在从 entry 出发的前半段；
  - `NO_EVIDENCE`：没有任何已核验的边。
- **block 为 FULL_CHAIN**，当且仅当两个 revision 都是 FULL_CHAIN。
- **报告**（没有成功门槛）：
  - 每个 fixture 的 k/10 和总体的 k/30，都附 95% Wilson 区间；
  - 各分类的分布；
  - golden 覆盖（只为与前几轮衔接）；
  - `unsupported` 的占比、novel 跳的数量（不做盲审：链的分类只依赖冻结的核验器和连接器）、花费。
  - 三个 fixture 不是「安全代码总体」的随机样本。
- **有效性**（按顺序判定）：
  - 连接器前置条件不满足：判为 `CONNECTOR_CALIBRATION_FAILED` 或 `PROTOCOL_INVALID`（见 §12.1）；
  - INFRA_INVALID 可以重跑，最多 3 次；
  - 任一 fixture 的 VALID block 少于 8 个，判为 `INCONCLUSIVE_INFRA`；
  - 出现上下文泄露、外部工具、harness 错误、scorer 拒绝了锁定的跳，或者冻结的核验器 / 连接器输出 hash 不一致，判为 `HARNESS_INVALID`；
  - 否则为 `REPORTED`。
- **措辞**：报告只说「fully VERIFIED chain」（被冻结核验器接受的链），不说「ground-truth correct chain」。P-Hybrid-1 的挑战集只为核验器提供了有限的安全证据，不能解释为现实世界中的零误报。
- **边界**：这只能说明「在当前**可表达的局部证据子图**内，agent 加核验器经常能组成完整的已核验链」，**不能**说明系统已经能从真实入口端到端地证明漏洞路径。
  - File Browser 的链只在 `getFiles` 内部；
  - Caddy 的链是挂载关系加 guard；
  - Authlib 的链是从 decode 的调用到 none 算法的 verify。

### 12.3 plumbing pilot（冻结前，只用合成代码）

- 用 Haiku 4.5 在 hopdev 的 Go 和 Python 模块上各跑 1 个 block，使用手选的 pilot 端点（`pilot_anchors.yaml`）。
- 两个 block 都是 FULL_CHAIN，harness 不变量全部为 0，CLI 的项目目录已清理。pilot 不计分。

### 12.4 暂缓与后续

- **完整性反馈 A/B（原 B）暂缓**：等到有新的、更长的 fixture，并且初稿不完整的比例足够高、原因也不都是同一个核验器盲区时再做。
- **真实入口（原 C）**：Go 跨函数调用、Python / Go 的参数绑定、定义 → 重新定义的 def-use 连接器，以及必要时配置 → 运行时的边界关系。这些作为**独立的 P-extension**，先做合成校准、单独预注册，**不在本轮加入**。

### 12.5 顺序

1. §12、连接器、链分类器、复现 runner 与 scorer、pilot → Codex 审查 → 冻结提交；
2. 连接器 cal 运行一次 → 提交；
3. 计算评估 fixture 的连接器输出 → 提交；
4. 运行 30 个会话 → 计分 → 提交 → 写报告。
5. 任何旧实验都不重新评分。

## 13. Completeness Repair（本分支最后一个行为实验；草案，未冻结）

**问题**（严格表述）：**在给定由 golden 导出的语义契约的条件下**，当 agent 的初始证据图已经确定不完整时，额外给一个不透露缺口位置、只有 1 bit 的完整性信号，能否提高把证据链补成 FULL_CHAIN 的概率？它**不**回答「agent 能否自己发现完整路径」。

**不回答的问题**：从真实入口出发的端到端证明（§12.0）、发现能力、三个 fixture 以外的普遍性。

**§13 完成后，无论结果如何，这条分支到此为止**：不再做更细的 prompt、schema 或反馈实验。之后转向独立的 P-extension（真实入口所需的关系），再到新 fixture 上做 1A 泛化。所有旧实验保持原判定，不重评分。

### 13.1 冻结复用

- 以下全部冻结复用：五类关系核验器（冻结输出 `experiments/hop_propose/frozen/`）；同一对象连接器（cal 安全 `097bd43`，评估输出 `fa3119a`，§12.1 的门槛照常执行）；§12 的链分类器与规则 G 端点；关系词表；P-Hybrid-2 的会话、校验、锁定和分叉机制。
- 不新增关系，不修改核验器，不修改 C2，不为 Caddy 或 File Browser 加特殊规则。全部是新会话，不复用 §12 的 run。
- **冻结的执行配置**：P-Hybrid-2 的全部 45 个会话在 meta 中记录的，以及 init 事件中实际服务的，都是以下配置：`claude-sonnet-5`、effort `high`、每个会话 `--max-budget-usd 3.0`、超时 1200 秒、Claude Code `2.1.280`。§13 的正式运行必须与之完全一致，并机械地检查两处：
  - runner：非 pilot 模式下，只要参数或本机 CLI 版本不一致，就拒绝启动；
  - scorer：检查每个 run 的 meta，以及 init 事件中实际服务的模型和 CLI 版本，任何偏差都判为 `PROTOCOL_INVALID`。
  - 因此两组之间唯一的实验差异，就是那一句话。pilot 可以使用 Haiku 和它自己的配置。

### 13.2 语义任务契约（两组相同，每个阶段都有）

- `get_task` 多出一项 `verification_contract`（`contract.yaml`）。它由两部分组成：一段通用规则（每跳接在上一跳的终点上；链从证据陈述的起点开始，到终点结束；如果陈述中的行为依赖于链上某个对象的一个性质，必须有一跳把这个条件挂到链上；`unsupported` 的跳不算链的一部分），以及该 fixture 的**冻结 golden 路径事实陈述，逐字照录**（有测试核对）。没有行号。
- **为什么用这些陈述**：一个纯通用的契约（「从提示的入口到那个行为」）与冻结的端点相矛盾。File Browser 的 entry 在 `getFiles`（125），不在提示的 `rawDirHandler` 里；Caddy 的 terminal 是挂载处，而不是决定行为的代码。按这种契约忠实作答的 agent 永远到不了 FULL。只有早已冻结的路径事实陈述与 FULL 的判据一致。
- **披露**：
  - 这些陈述是很强的语义提示（写出了 `deserialize_compact`、`nameInArchive`、「matches 2xx」）。
  - §13 因此是**新的接口**，初稿的 FULL 比例**不能**与 §12 的 18/30 比较。
  - 它可能大幅减少初稿不完整的情况，§13.5 的上限与 `INCONCLUSIVE_OPPORTUNITY` 就是为此准备的。

### 13.3 共享初稿与分叉

- 与 §11 相同：初始会话锁定后，状态复制成不可变快照；两组同时用 `--resume --fork-session` 分叉；§11 的全部隔离不变量都适用。
- **只有初稿不完整的 block 才分叉。**
- control 收到 P-Hybrid-2 的修订消息，逐字照录。
- treatment 收到的是 control 的消息加上一个空行和一句话（有测试核对这是唯一的差别）：
  > `The currently submitted evidence is not complete under the verification contract.`
- 因为只有不完整的初稿才分叉，这句话出现时必然为真。treatment 不会得到缺了哪一跳、哪种关系、哪个节点、哪一类缺口、golden 路径，或推荐的下一跳。
- 两组各只允许一次最终提交，没有第三轮。

### 13.4 FULL_CHAIN 判据与资格

- 「完整」**就是**冻结的 §12 分类器在两个 revision 上都判为 FULL_CHAIN。QUALIFIER_GAP 也算不完整：只有 entry → terminal 连通、却缺少必要的安全条件，不算完整。
- runner 在分叉之前，用同一个分类器判定初稿，并把判定结果记下来。scorer 会重新计算；两者不一致、或者分叉与否与资格不符，都属于 harness 违规。

### 13.5 机会抽样与停止规则

- **主要 fixture**：Caddy 与 File Browser。各自的目标是 **K = 12 个完整的合格配对**（初稿不完整，并且两个子会话都是 VALID），上限是 **M = 30 个 VALID 初始会话**。
- **Authlib**（天花板 fixture）：只跑 **N = 5** 个初始会话，报告初稿的 FULL 比例。如果它的初稿不完整，照样分叉，结果只作次要报告，不进入主要分析。
- 各 fixture 按每轮用固定种子（20261002）打乱的顺序轮流运行，已达到目标的 fixture 退出。停止规则只读取**处理之前**的信息（初稿是否完整、已完成的配对数），从不读取任何一组的结果。
- 重跑规则：INFRA_INVALID 的初稿最多重跑 3 次，不计入上限；子会话失败重试 3 次仍不成的配对不计入 K，由后续抽样补足。遇到额度耗尽，整批停止，恢复后按磁盘上的状态继续。
- 达到上限 M 时仍不足 K 个配对，就是机会不足。
- **离散效应量表**（`experiments/hop_repair/power.py`，精确计算）：

```
P(SUCCESS) by eligible pairs per fixture K (pooled 2K) and (P(T_only), P(C_only)):
   K  (0.00,0.00)  (0.10,0.10)  (0.15,0.05)  (0.25,0.05)  (0.35,0.05)  (0.50,0.05)
   6        0.000        0.002        0.016        0.104        0.277        0.577
   8        0.000        0.005        0.043        0.211        0.450        0.755
  10        0.000        0.009        0.079        0.314        0.585        0.866
  12        0.000        0.012        0.118        0.405        0.692        0.932
  15        0.000        0.016        0.174        0.525        0.813        0.976
```

  - 约 1% 是在 (P(T_only), P(C_only)) = (0.10, 0.10) 这个**具体的**无效应情形下、无条件地判为 SUCCESS 的概率（之所以低，是因为每个 fixture 还要求 T_only ≥ C_only），不是在所有无效应情形下统一成立的第一类错误率。
  - K = 12 时，能以约 70% 的把握检出 T_only 35% 对 C_only 5% 的效应；T_only 25% 时约为 40%。
  - 名义花费估算约 $50–70（按 §12 与 P-Hybrid-2 的单会话花费，假设初稿不完整的比例约一半）。

### 13.6 主要分析与判定

- **每个合格配对**记为以下之一：T_only（只有 treatment 的最终提交是 FULL）、C_only（只有 control 是 FULL）、Both、Neither。Caddy 与 File Browser 分别报告，不只报告合计。
- **判定**（按顺序）：
  1. `PROTOCOL_INVALID`：连接器门槛或冻结输出不满足（§12.1），或者有任何 run 偏离了冻结的执行配置（§13.1）；
  2. `HARNESS_INVALID`：出现任何隔离、泄露、外部工具、harness 错误、scorer 拒绝锁定的跳，或资格不一致；
  3. `RUN_INCOMPLETE`：有 fixture 既没达到目标、也没达到上限，也就是还没跑完（例如因额度暂停）。这不是一个结论；
  4. `INCONCLUSIVE_OPPORTUNITY`：任一主要 fixture 达到上限 M 时仍不足 K 个配对；
  5. `SUCCESS`：合计（Caddy + File Browser）的不一致配对上，单侧精确符号检验 p ≤ 0.05，**并且**每个主要 fixture 都有 T_only ≥ C_only；否则为 `FAIL`。
- **次要指标**只用来解释机制，不影响判定：
  - 缺口类别的转移（例如 QUALIFIER_GAP → FULL）；
  - 新增的已核验跳、删除的 UNVERIFIED 或 `unsupported` 跳；
  - 最终跳数与 `unsupported` 占比；
  - 各 fixture（含 Authlib）初稿的 FULL 比例。

### 13.7 plumbing pilot（冻结前，只用合成代码）

- 用 Haiku 4.5 在 hopdev 的 Go 和 Python 模块上各跑 1 个 block（pilot 契约与 pilot 端点），用 `--force-fork` 强制分叉（`results/completeness-repair-pilot.json`）。
- hopdev-go 的初稿确实不完整（head 为 ENTRY_GAP），自然分叉，结果为 Both；hopdev-py 的初稿是 FULL，强制分叉。
- harness 不变量全部为 0；两条消息只差那一句话；契约确实出现在 `get_task` 中；CLI 的项目目录已清理。pilot 不计分。

### 13.8 局限

- 契约是强提示（§13.2），效应估计只针对「在这个契约之下」。
- 只有两个主要 fixture、最多 24 对，只能检出较大的效应。
- 这里的 FULL_CHAIN 指被冻结核验器接受的链，不是 ground truth；而且只限于可表达的局部证据子图。

### 13.9 顺序

§13 连同代码和 pilot 送 Codex 审查 → 冻结提交 → 按机会抽样运行 → 计分（在查看细节之前提交）→ 写报告。

## 14. P-extension：从 Spike P 真实入口接到 §12 局部子图（provider-only；草案，未冻结）

**问题**：新增的三个通用 relation（实现四个所需的语义步骤），能否用冻结核验器判为 VERIFIED 的跳，把早已冻结的 Spike P source 端点（真实入口）接到 §12 已经核验过的局部子图上，使三个当前 fixture 的每个 revision 都成为从真实入口到 §12 terminal 的 FULL_CHAIN？每种新关系是否安全（假跳从不判为 VERIFIED，真跳从不判为 CONTRADICTED）？

- **不调用 LLM**：跳由作者按规则写出，与核验器一同冻结，再由核验器判定。这不是 agent 实验。
- **不回答的问题**：
  - agent 能否自己找到这些跳；
  - 需要哪些证据（requirement discovery，留给 1A）；
  - 三个 fixture 以外的普遍性；
  - 配置 → 运行时的边界（Caddy 的 directive token、map 变更、模块注册表）。
- **§14 之后，三个当前 fixture 退役**：不再在它们上面做任何行为实验。所有旧实验保持原判定，不重新评分。

### 14.1 冻结的输入与不做的事

- **真实入口就是 Spike P 的 source 端点**（`experiments/provider_reach/endpoints.yaml`，§9 起冻结），不重新定义：
  - Authlib：`jwt.py:80` 的参数 `s`；
  - Caddy：`handler` 的定义（base 185 / head 211）；不取 directive token、map 变更或模块注册表；
  - File Browser：`filenames` 的定义（base 165 / head 171）。
  - 写成节点身份，放在 `experiments/hop_bridge/entry_anchors.yaml` 中（有测试核对文件和行号与 `endpoints.yaml` 一致）。
- **§12 的局部锚点不变**（`experiments/hop_chain/anchors.yaml`）：entry、terminal 与 `needs_qualifier` 都照旧，只有链的起点从 §12 的 entry 换成真实入口。
- **冻结复用**：
  - P-Hybrid-1 的五类核验器，以及它们在当前 fixture 上的冻结输出（`experiments/hop_propose/frozen/`，使用前按 manifest 核对 hash）；
  - 同一对象连接器（cal `097bd43`，评估输出 `fa3119a`；§12.1 的门槛照常执行）；
  - §12 的链分类器；
  - 当前 fixture 的 CodeQL 数据库：产生那些冻结输出的同一批数据库（`runs/hop_propose/analysis/`），CodeQL 2.27.1。
- **不做的事**：
  - 不改 source 端点，不改 §12 的局部锚点；
  - 当前 fixture 上某一段接不上时，**不加第五、第六种关系**，只记为能力缺口；
  - 不为当前 fixture 修改核验器；不重新评分。

### 14.2 三个 relation，实现四个所需语义步骤（`experiments/hop_bridge/relations.yaml`）

| 语义步骤 | 跳关系 | 语言 | from 的节点种类 | to 的节点种类 |
|---|---|---|---|---|
| def-use 延续 | `def_use` | Go、Python | Go：definition、parameter、range_value；Python：parameter、definition | Go：definition、call_argument；Python：definition、call |
| 参数 / 实参绑定 + 跨函数调用 | `argument_binding` | Go | call_argument | parameter |
| 集合 → 循环 / range 元素绑定 | `range_element` | Go | definition、parameter | range_value |

- **为什么「跨函数调用」与「参数 / 实参绑定」合成一个 relation**：单独的「调用 → 被调函数体」关系会丢掉「是哪一个实参携带了这个值」。链只能再靠「函数 → 其中的节点」连接器接到函数里的**任意**节点，也就是任意一个形参。把调用解析放进 `argument_binding`，就能同时核验「这次调用运行的是这个函数」和「第 i 个实参绑定到第 i 个形参」。
  - 因此这**不是**对两种能力分别做了独立验证，而是一个复合 relation。报告只说「静态调用目标加按位置的实参绑定这个 relation 为 SUPPORTED / PARTIAL」，不分别声称「跨函数调用已支持」和「实参绑定已支持」。
- **真值条件**（逐字见 `relations.yaml`）：
  - **`def_use`**：`from` 定义一个值（局部定义、形参，或 range 的 value 变量）。`to` 是函数内之后的一个定义（右侧读取了这个值），或一个调用实参（其表达式读取了这个值）；读取经由函数内的局部值流。Python 版只接受单名定义；`to` 也可以是一个调用，只要它的某个位置实参或关键字实参读取了这个值。
  - **`argument_binding`**：`from` 是一次调用的第 i 个实参；这次调用在运行时**能够**执行某个函数，`to` 是该函数的第 i 个形参。变长参数的尾部接收的是切片，而不是这个实参，因此不算。真值是语义的，**核验器只跟随静态解析**（有函数体的静态目标）：经接口动态分派或函数值能到达的函数，都是它会留为 UNVERIFIED 的真跳。
  - **`range_element`**：`from` 定义一个集合（局部定义或形参）；`to` 是某个 `range` 的 value 变量，这个 range 所遍历的表达式经局部值流就是这个值。单变量的 range 绑定的是索引，不是元素。
- **契约与 P-Hybrid-1（§10.2）相同**：
  - CONTRADICTED 只来自封闭的形状检查（端点在所声称的 revision 的语法树中，没有指向允许种类的节点）；
  - 关系本身的检查只给出 VERIFIED 或 UNVERIFIED；
  - 查询中不出现任何 fixture 的名字、文件或行号（有测试检查）。
- **实现**（`experiments/hop_bridge/queries/{go,python}/`，CodeQL 2.27.1）：
  - Go 的 `def_use` 与 `range_element`，从 `from` 所做的显式 SSA 定义出发，用 `DataFlow::localFlow` 求值流；
  - `argument_binding` 要求 `call.getTarget().getFuncDecl()` 有函数体、形参序号相同，并且不在变长尾部；
  - Python 的 `def_use` 从形参节点或定义的名字出发，用 `localFlow` 求值流，定义自身的目标不算读取。
- **披露（范围）**：实现并测试过的语言覆盖是**不对称的，按 fixture 需求决定**。
  - Python 只实现了 `def_use`，因为 Authlib 的桥只需要它；
  - `argument_binding` 与 `range_element` 只有 Go 版。
  - 不为形式上的对称提前补齐。之后在新 fixture 上（1A），如果需要的 relation 没有 provider 支持，就自然记为 unsupported 盲区。
  - `def_use` 与 `range_element` 只做函数内的局部值流，不经过堆、全局变量或闭包捕获；跨函数只靠 `argument_binding` 这一步。

### 14.3 三个集合

- **dev**（`fixtures/_bridgedev/build.py`：`bridgedev-go` `6670bc5`，`bridgedev-py` `1b33f71`；与三个当前 fixture 没有共享代码）：
  - 30 跳，15 真 15 假（wrong_target 7、wrong_source 5、reversed 3）。核验器只在 dev 上开发。
  - 冻结前的结果只作参考（`results/p-extension-dev.json`，按核验器分类，见 §14.5）：
    - `codeql/go/def_use`：SUPPORTED，4/4；`codeql/python/def_use`：SUPPORTED，6/6；
    - `range_element`：SUPPORTED，2/2；
    - `argument_binding`：PARTIAL，2/3。漏掉的 g16 是接口动态分派，按设计留为 UNVERIFIED。
    - 假跳 0/15 被判为 VERIFIED；4 个假跳被形状检查判为 CONTRADICTED（3 个 reversed，1 个单变量 range）。
- **cal**（`fixtures/_bridgecal/build.py`：`bridgecal-go` `5972c62`，`bridgecal-py` `1ef141d`；执行留出的校准 / 挑战集）：
  - 在任何桥核验器运行之前写好；跳 id 不透明（c01–c30），真值中保留描述名。
  - 30 跳，17 真 13 假（wrong_target 8、wrong_source 3、reversed 2）：
    - Go 20 跳：`def_use` 5 真 2 假，`argument_binding` 5 真 3 假，`range_element` 2 真 3 假；
    - Python 10 跳：`def_use` 5 真 5 假。
  - 挑战内容：
    - 同时绑定索引和值的 range；
    - 先复制到另一个变量再遍历的集合；
    - 内层块中的同名遮蔽；
    - 闭包调用（函数值；真跳，核验器预期留为 UNVERIFIED）；
    - 接口分派（真跳，预期留为 UNVERIFIED）；
    - 交换顺序的实参；
    - Python 中形参被重新赋值；
    - 同名形参的内嵌函数；
    - 关键字实参。
  - 冻结后只运行一次。
- **current**（三个当前 fixture；`sets/current.yaml`，跳 id 不透明 b01–b95，以固定种子 20261003 排序）：
  - 95 跳，15 真 80 假（shift 30、wrong_target 26、reversed 15、wrong_revision 9，其中 9 个预期被引用检查拦下）。
  - 冻结前删除了 6 个重复项：Authlib 与 File Browser 的 `f4` 在两个 revision 中代码完全相同，wrong_revision 与另一侧的真跳重合；记在 `dropped_before_freeze` 中。
  - **真跳**：作者读代码，沿真实入口到 §12 entry 的路径写出。每个 revision 的真跳恰好首尾相接，构成从真实入口到 §12 entry 的一条链，而且每个真跳都在链上（有测试检查）。

    | fixture | revision | 链 |
    |---|---|---|
    | Authlib | base / head | 参数 `s`（80）→ `def_use` → `s = to_bytes(s)`（101）→ `def_use` → `deserialize_compact(...)` 调用（104，§12 entry） |
    | File Browser | base / head | `filenames` 的定义（165 / 171）→ `range_element` → `fname`（178 / 184）→ `def_use` → `getFiles` 的实参 `fname`（179 / 185）→ `argument_binding` → 形参 `path`（112）→ `def_use` → `nameInArchive` 的定义（125，§12 entry） |
    | Caddy | base | `handler` 的定义（185）→ `object_composition` → `Routes` 写入（198，§12 entry） |
    | Caddy | head | `handler` 的定义（211）→ `def_use` → `copyHeaderRoutes = append(..., caddyhttp.Route{...handler...})`（218）→ `object_composition` → `Routes = append(..., copyHeaderRoutes...)`（233，§12 entry） |

  - **Caddy 用到了冻结的 `object_composition`**，因为它的 §12 entry 本身就是一次字段写入：
    - base：`handler` 是 `Route` 字面量中调用实参的一部分，按真值条件是「直接部分」；
    - head：`copyHeaderRoutes...` 是被追加的实参。
    - 这些跳（2 真 12 假）用 P-Hybrid-1 的冻结输出判定。
  - **假跳**：按 §10.4 的四条规则生成：
    - 节点按（行，列）排序，取最近的允许种类的节点（因此可以取同一行上的相邻实参或形参）；
    - 按真值条件实际为真的候选跳过并记为 `skipped_true`；
    - 每个假跳都写明理由，冻结前由人工确认；运行之后不删除任何负例。
  - 与 §10.3 相同：跳、真值和核验器都出自同一作者，而作者读过这些代码和 golden。防护措施：核验器必须通用；current 的跳和变异在任何桥核验器接触 current 之前按规则写好，并与核验器一同冻结；节点种类靠人读代码识别，冻结前不在 current 上运行任何桥查询。

### 14.4 链的判定

- **局部部分已经闭合**：P-Hybrid-1 eval 集中的 golden 局部真跳（Authlib 各 2 个，Caddy 各 2 个，File Browser 各 1 个），在冻结输出上全部是 VERIFIED。它们在六个 revision 上都已构成从 §12 entry 到 terminal 的 FULL_CHAIN（Caddy 含 guard；有测试检查）。因此，链没有闭合，只可能是桥这一段的原因。
- **`bridge.py chain`**：对每个 fixture 和 revision：
  - 边 = 被判为 VERIFIED 的真桥跳，加上上面的 golden 局部真跳；
  - 用冻结的 §12 分类器（Go 加上冻结的同一对象连接器），从真实入口分类到 §12 的 terminal；
  - 分类结果为 FULL_CHAIN / QUALIFIER_GAP / ENTRY_GAP / INTERNAL_GAP / NO_EVIDENCE。
- 图中只放真跳：这是对已知真证据的闭合检查，不是提议实验。假跳的安全性由关系分类衡量；任何假跳被判为 VERIFIED，判定都已经是 UNSAFE（§14.6）。

### 14.5 指标与分类

- **分类单位是具体的核验器实现**，键为 `provider/语言/关系`，例如 `codeql/go/def_use`、`codeql/python/def_use`。每个键对应唯一一个查询文件，记在结果的 `verifier_queries` 中。
  - Go 与 Python 的 `def_use` 虽然名字相同，却是不同语言、不同查询、不同的 AST 与数据流模型，支撑的也是不同的当前 fixture。合在一起算，Python 的 BLIND 会被 Go 的结果掩盖成 PARTIAL，也就是一种语言替另一种语言兜底。
  - 按关系名合并的汇总只放在 `report_only_by_relation` 中供报告使用，**判定从不读取它**（有测试检查）。
- 每个核验器都使用 P-Hybrid-1 的 `score_states`（§10.5）分类：
  - UNSAFE（有假跳被判为 VERIFIED，或者有真跳被判为 CONTRADICTED）、INCONCLUSIVE_TOOL_FAILURE、SUPPORTED、PARTIAL、BLIND；
  - 另外报告按变异规则分的假跳状态，以及被引用检查拦下的数量。
- current 的分类也包括 Caddy 用到的冻结 `codeql/go/object_composition`：闭合的链同样依赖它。

### 14.6 判定（`bridge.py decide`）

按顺序，取第一个成立的：

1. `UNSAFE`：任一核验器在 cal 或 current 上是 UNSAFE（包括 current 上的 `codeql/go/object_composition`）。
2. `INCONCLUSIVE_TOOL_FAILURE`：任一核验器在 cal 或 current 上是 INCONCLUSIVE_TOOL_FAILURE。
3. `CALIBRATION_BLIND`：任一预注册的 §14 核验器（`codeql/go/def_use`、`codeql/go/argument_binding`、`codeql/go/range_element`、`codeql/python/def_use`）在留出的 cal 上是 BLIND（没有一个真跳被判为 VERIFIED），或者缺少 cal 结果。
   - 必须具备的核验器清单取自冻结的 `relations.yaml`，而不是结果文件里实际出现的键（有测试检查）。
   - 这些查询是在看过当前 fixture 的需求之后写的，「不是只为当前代码特调」这一约束由留出的 cal 承担。
   - 一个在 cal 上一个真例都没核验出来的核验器，即使恰好接受了 current 上的已知真跳，也只能说明「它碰巧接受了这一跳」，不能说明这个通用 relation 得到了校准的支持。
   - 这与「current 的链闭合不了」是两种不同的失败，所以单独命名，并且排在 `CAPABILITY_GAPS` 之前：核验器连最低限度的留出校准都没有通过时，不能用 current 上的失败去解释具体缺了什么能力。
4. `CAPABILITY_GAPS`：有 revision 不是 FULL_CHAIN。逐个列出分类，记为能力缺口；**不**因此新增关系。
5. `LOOP_CLOSED`：六个 revision 全部是 FULL_CHAIN。

- **cal 上的 PARTIAL 不阻断**，照实报告盲区（例如 `argument_binding` 对接口分派和函数值的盲区）。不设 80%、60% 之类的覆盖比例：样本很小，各 relation 的性质也不同。对 cal 的要求只是：至少核验出一个真实正例，没有安全失败，也没有工具失败。current 上的 PARTIAL 或 BLIND 同样照实报告；当前 fixture 上的覆盖由链的闭合来衡量。
- **负例不因结果修改**：例如 `handler`@211 → `Routes`@233（跨过 218 这一步真实的中间组合，不算单步）。如果冻结的 `object_composition` 把它判为 VERIFIED，就照协议判为 `UNSAFE`。
- cal 未通过时，current 不运行（§14.8），判定只由前三条中的一条给出。
- **措辞**：`LOOP_CLOSED` 只说明「冻结核验器接受了一条从 Spike P source 到 §12 terminal 的链，其中每一跳都是作者写出的已知真跳」，**不**说明漏洞路径已经被端到端证明：
  - 这条链仍然限于可表达的局部证据；
  - 需要哪些证据，来自 golden 和作者。

### 14.7 局限

- 跳由了解代码和 golden 的作者写出。这里测的是核验器能否接受并闭合已知的证据，不是发现能力。
- 负例是相关的变异挑战，不是随机样本。各项比率只描述本集合。
- 语言覆盖不对称，按 fixture 需求决定（§14.2）。
- `argument_binding` 是一个复合 relation（静态调用目标加按位置的实参绑定），只跟随静态解析；接口分派和函数值是盲区。
- 值流只在函数内（`def_use`、`range_element`）；跨函数只有 `argument_binding` 的一步绑定。

### 14.8 顺序

1. §14、代码、dev 结果、测试 → Codex 审查 → 冻结提交。冻结内容包括：两个合成模块的构建脚本、集合、真值、查询、`relations.yaml`、`entry_anchors.yaml`、`bridge.py`、测试。
2. cal 运行一次 → 计分 → 提交（在查看细节之前）。
3. **cal 是 current 的硬性前置条件**：
   - cal 出现 UNSAFE、INCONCLUSIVE_TOOL_FAILURE 或 CALIBRATION_BLIND 时，current **不运行**，`decide` 只依据 cal 给出判定。这时 current 的结果不可能改变判定，运行它只会产生诱人重新解释的数据。
   - cal 通过时：current 运行一次 → 计分 → `chain` → `decide` → 提交（在查看细节之前）。
4. 写报告。报告中按关系名合并的汇总一律标为 report-only aggregate，不作为校准单位。
5. `bridge.py` 机械地执行上述约束：
   - cal 和 current 只在工作树干净时运行，已有结果时拒绝再跑；
   - current 启动前检查：cal 结果存在，cal 没有上述三种失败，并且 cal 运行时记录的文件（查询、`relations.yaml`、`bridge.py`、cal 集合）的 hash 未变；
   - provenance 中记录 harness commit，以及查询、集合和 `bridge.py` 的 hash。
6. 然后三个当前 fixture 退役：除了已冻结流程中的 P-Hybrid-2 盲审，不再用它们做新的研究设计或 agent 行为实验。

## 15. RD：新 fixture 上的证据需求发现（实验宪法；已冻结）

讨论中一直称这一阶段为「1A」，但它与 §0 / §5 的 1A（结构候选的信噪比）不是同一个问题。为避免混淆，下文称为 **RD**（requirement discovery）。

**问题**：在没见过的代码上、没有由 golden 导出的契约时，系统自己知不知道需要证明什么？分三步，依次锁定，分别评分：

- **A：需求发现**。agent 能否选对 entry、behavior 和必要的限定条件？
- **B：实现**。在 agent 自己锁定的需求之下，hybrid 系统能否形成每一跳都被核验的证据链？
- **C：归因**。根据得到的证据，最终归因是否正确？另设只评 C 的负对照（§15.6）。

**定位**：这是**第一批新 fixture 上的泛化研究**（first fresh-fixture generalization study），不估计「真实安全修复总体」上的表现。

**本节只是宪法**：只规定选择 fixture、定义与裁决真值、需求 schema、任务与负对照、A → B → C 的锁定顺序，以及 unsupported 的处理。
- 本节冻结之前，不看任何候选 fixture，不运行任何 agent。
- 具体的 agent 协议（prompt、工具、上限、会话数、执行配置）在 §15.10 的第 6 步另行预注册。

**不做的事**：
- Authlib、Caddy、File Browser 已退役，不参与 RD 的任何设计或测量。
- 不改写任何旧实验的结果。
- RD 期间不扩展关系词表或限定条件类型，也不修改核验器。

### 15.0 动机：R016

P-Hybrid-2 的盲审中，同一个 `object_composition` 跳（Caddy head 的 218 → 233）：
- 作者与 Codex 判为真，§14 的闭合依赖这个真值；
- 独立的盲审者按同一份冻结定义，判为假。

两种读法都说得通：分歧在于「一步组合」里的「存入」是否包括追加到局部切片。这**不是**核验器错了，也不是审阅者错了，而是**关系定义的边界不可判定**。

旧结果不因此改变：§14 保持 `LOOP_CLOSED` 并已注明争议，P-Hybrid-2 的标签也不改。但 RD 的真值不能再是「作者说是真的就是真的」。

### 15.1 真值的可采性（truth admissibility）

每一条真值都要走完这条流程，才能进入主要指标：

`候选真值 → 边界规格检查 → 独立裁决 → 可采的真值`

**1. 操作性定义与边界用例**（合成代码，不来自任何 fixture）：
- RD 词表中的每种关系、每种限定条件类型（§15.4），以及 entry / behavior 的定义（§15.3），都要有**操作性定义**；
- 容易出现歧义的边界，要有写明预期标签的正例和反例。至少包括：
  - 容器展开组合（R016，定义见下）；
  - 接收者别名（receiver alias）是否允许；
  - 兄弟字段上的性质算不算限定条件；
  - 接口分派与静态调用；
  - 闭包捕获；
  - 一次定义多个变量；
  - 值拷贝与指针。
- **R016 的边界采用读法 A（Codex 决定）**：如果一个容器值 `src` 被直接用作展开 / 变长实参，参与一次把它的元素组合进 `dst` 的操作（例如 `dst = append(dst, src...)`），那么 `src → dst` 是一个 `object_composition` 跳；元素此前如何进入 `src`，是另一个独立的前序跳。
  - 这是一般的「容器到容器」组合定义，不引用任何 fixture。
  - 由此，定义 `src` 的语句 → 展开存入处算一跳；元素的定义 → 展开存入处是两跳，不能折叠。
  - 采用它的理由是它与「值流」的一般用法一致，而**不是**因为它与冻结的核验器一致。它同样要经过下面的可判定性检验：如果独立裁决仍不能稳定接受，这个边界就记为 `INDETERMINATE`，不再为了迁就核验器修改定义。
- 边界用例由作者在看到任何 fixture 之前写好。

**2. 可判定性检验**：
- 两个独立的裁决者（见第 4 条）只看定义和代码，逐个标注边界用例；不看作者的标签、核验器的结果或任何模型输出。
- 某个用例的裁决与作者的标签不一致时，作者可以修订一次定义的文字（这时还没有任何 fixture 参与）。之后由**两个新的**裁决会话，重新标注该关系或类型的**全部**边界用例，不能沿用第一轮的会话。
- 仍不一致时：
  - 这个边界成为明写的 `INDETERMINATE` 区域：以后落在这个区域里的跳和需求项，一律记为 `INDETERMINATE_TRUTH`；
  - 如果不一致落在该关系或类型的核心用例上（而不只是边界），它**退出 RD 的主要词表**。

**3. 核验器一致性**（核验器冻结不改）：
- 在边界用例上，用可采标签重新运行冻结的核验器。
- 有可采为假的用例被判为 VERIFIED，或者可采为真的用例被判为 CONTRADICTED，这个核验器就与操作性定义不一致。它所属的关系退出 RD 的主要词表：该关系的跳一律视为 unsupported。
- 不因此修改核验器，也不为了让核验器一致而倒过来选择定义。

**4. 裁决者**：
- 找不到独立的人（P-Hybrid-2 已确认）。因此裁决由**两个彼此独立的全新模型会话**完成：
  - 两个会话都不能是 Claude（被测 agent 的家族）；
  - 最好来自两个不同的非 Claude 模型家族；如果实际上只有 ChatGPT，就用两个独立的会话（Temporary Chat 或关闭 memory），并在报告中注明它们不是统计上独立的模型家族；
  - 两个会话互相看不到对方的答案，顺序随机；每批材料都用新会话。
  - **一批材料就是一个 fixture 的全部候选项（含干扰项）**，或一种关系 / 类型的全部边界用例。审阅表由脚本自动生成并脱敏，标签以结构化格式收集。
- 如果以后能找到独立的人，由人担任其中一个裁决者。
- 裁决者只看操作性定义和代码上下文；对需求真值，还看公告、修复 diff 与执行真值（§15.3）。永远不看 agent 的输出、核验器的结论或作者的预期标签。
- **干扰项**：
  - 交给裁决者的候选项中，按规则混入干扰项：对作者的锚点做 §10.4 式的就近移动，对限定条件替换 `kind`，并在某个 revision 上翻转 present / absent（§15.4）。
  - 裁决者不知道哪些是作者的项，只对每一项标注 `REQUIRED`、`NOT_REQUIRED` 或 `INDETERMINATE`。
  - 裁决者还可以指出他认为缺失的必需项，**必须按 §15.4 的需求格式写出**（`kind` 与锚点）。处理见第 5 条的完整性核对。

**5. 可采与不一致**：
- **只有作者、裁决者 A、裁决者 B 三方一致时，一条真值才可采。** 任何不一致都不投票，也不由任何一方裁定，一律记为 `INDETERMINATE_TRUTH`。
- `INDETERMINATE_TRUTH` 从主要的 precision / recall 中**排除**，在附录中做敏感性分析：各种读法各算一遍。
- **真值完整性核对**（在任何 agent 接触 fixture 之前；防止「作者漏写的项被排除，反而抬高 recall」）：
  - **等价**是机械判定的，不由作者判断：两个裁决者指出的缺失项，只有**完整的需求身份**相同时才算同一项，即以下全部相同：
    - `kind`（或同为 entry / behavior）；
    - 全部参与评分的语义字段（guard 与 transform 的 `expected`，config 的 `expected_condition`）；
    - 每个锚点槽在每个 revision 上的 `state`；
    - 每个 present 的锚点与每个 absent 的 context，使用与正式 matcher 相同的冻结规则比较（节点身份，Go 另加冻结的同一对象连接器）。
  - 指向同一位置、但语义相反的两个缺失项（例如一个是 `must_hold`，一个是 `must_not_hold`），**不是**同一项：它们各自按「只被一个裁决者指出」处理。
  - 指出的缺失项必须通过 §15.4 的结构校验（锚点能解析等）。不通过时，退回同一个会话一次，只修格式、不改内容；仍不通过的，按「只被一个裁决者指出」处理。
  - 只有一个裁决者指出的缺失项：记为 `INDETERMINATE_TRUTH`，计入该 fixture 的**歧义负担**（ambiguity burden），并在敏感性分析中按「必需」计入 recall 的分母，单独报告。
  - 两个裁决者独立指出同一个缺失项：这个 fixture 的需求真值判为 `INCOMPLETE_TRUTH_SPEC`。
    - 作者可以在 agent 接触之前**修订一次**该 fixture 的需求真值；
    - 修订后，由**两个新的**会话重新裁决这个 fixture 的**全部**需求项（含干扰项）；只有新一轮三方一致的项可采；
    - 新一轮中两个裁决者又独立指出同一个缺失项时：缺的是 entry 或 behavior，这个 fixture 不可采，按 §15.2 替补；缺的是限定条件，这个 fixture 的限定条件层不可采（不进入 qualifier 的 recall / precision，entry、behavior 与 C 照常计分），不替补，照实报告。
- **防止排除偏倚**：
  - 报告每个 fixture 被排除的比例；
  - 一个 fixture 的 entry 或 behavior 只要是 `INDETERMINATE_TRUTH`，这个 fixture 就不可采，按 §15.2 的预留队列替补；
  - 全部限定条件中，`INDETERMINATE_TRUTH` 超过三分之一时，报告为「词表定义失败」。
- **可采锚点集合中的每一个锚点都要单独经过裁决**。锚点集合与 hash 在 agent 第一次接触 fixture 之前冻结；之后不能为了匹配 agent 的输出，往集合里追加「等价」位置。

**6. 冻结**：上面这些全部在任何 agent 接触 fixture 之前完成，可采真值连同 hash 一并冻结。

### 15.2 fixture 的选择

**原则**：先冻结抽样框架，再看候选；机械筛选，按固定种子排序；拒绝逐个记录理由；**绝不因为 provider 支持某种关系而入选或替换**。

**1. 抽样框架**：
- OSV 中 **Go** 与 **PyPI** 生态的公告（这是现有 provider 支持的两种语言）。
- 发布时间（OSV 的 `published` 字段）在 `[2026-01-01T00:00:00Z, 2026-09-30T00:00:00Z)` 之内。
- 数据库会事后变化，因此选择开始时下载一次 OSV 的 Go 与 PyPI 数据快照，记录 hash 并提交；候选池必须能从这份快照完全重建。
- 不以模型的知识截止日期作为硬条件，因为被测模型没有可审计的截止日期；记忆污染列为局限。

**2. 机械筛选**（脚本执行，结果全部留档）：
- 公告引用了公开 git 仓库中可定位的修复 commit，由此确定修复后的 revision；修复前的 revision 取它的父 commit；
- 修复改动了该语言的源文件，不是只改依赖声明（`go.mod`、`requirements*.txt`、`pyproject.toml` 之类）；
- 去掉测试文件后，修复 diff 不超过 200 行；
- 排除 authlib、caddy、filebrowser 三个仓库；
- 同一仓库最多入选一个。

**3. 排序**：通过机械筛选的候选，按固定种子（冻结时写定）打乱，每种语言各排成一个队列。

**4. 人工可采条件**（事先列明，逐个记录接受或拒绝的理由）：
- 可以得到**执行真值**：修复 commit 中的回归测试、公告中的 PoC，或者能在限定时间内独立构造的 probe；并且实际运行确认修复前有该行为、修复后没有；
- 能在本地构建和运行，不需要外部商业服务或特殊硬件；
- 漏洞在该仓库自己的代码中，不在 vendored 的依赖里；
- 覆盖配额：同一个 CWE 大类最多两个（按全部入选 fixture 计）。
- **禁止的理由**：「provider 能 / 不能表达这条路径」。候选被接受之前，不在它上面运行任何核验器或 provider 查询。

**5. 规模与预留队列**：
- 每种语言按队列顺序检查，直到有 **4 个主用 + 2 个预留** 通过人工可采条件（并满足配额）；主用是最先通过的 4 个。
- 冻结的是这份**有序的可采队列**（主用加预留），以及完整的拒绝日志；都在写任何真值之前提交。
- **替补只有一种触发条件**：主用 fixture 的 entry 或 behavior 成为 `INDETERMINATE_TRUTH`（§15.1）。这时只能取同一语言队列中的下一个预留，而且仍要满足 CWE 配额。provider 的限制、实现上的困难，都**不能**触发替补。
- 预留用尽时，N 就相应缩小。不能重新筛选，也不能为了凑够 8 个而放宽 200 行、CWE 配额或任何其他条件。
- 目标 N = 8（Go 与 Python 各 4 个）。

### 15.3 真值（都不给 agent 看）

**1. 需求真值**（用于 A）：entry、behavior 和必要的限定条件。
- 由作者依据公告、修复和执行真值写出，再经 §15.1 的裁决。
- 每一项允许列出一个**可采锚点集合**，用来吸收等价的锚法（例如形参本身，与它的第一次定义）；集合中的每个锚点都单独裁决（§15.1 第 5 条）。匹配时使用节点身份；Go 另外可以使用冻结的同一对象连接器。
- 操作性定义：
  - **entry**：主张中所说的攻击者可控输入，在本仓库代码中**第一次成为一个值**的位置。例如对外处理函数的形参，或者从请求、配置、令牌对象中读出它的那次定义。
  - **behavior**：对于触发输入，**决定安全相关效果**的程序点。修复改动的是一处检查或变换时，就是这处检查或变换；修复改在别处时，是受影响的 sink 语句。某个 revision 上没有对应的语句时（例如修复新增了检查，或删掉了 sink），这个 revision 记为 absent（§15.4）。
  - 这两条定义同样要有边界用例，并经过 §15.1 的可判定性检验。

**2. 实现真值**（用于 B 与 C，只用于评分）：
- 执行真值：PoC 或测试在两个 revision 上的结果；
- 期望的归因：沿用 §1.1 的归因表（由 scorer 把中性的 revision 名还原为修复前 / 修复后）。例如对真实的 advisory 主张，期望 `FIX_IMPLICATED`；
- 参考证据：作者写出、并经冻结核验器检查的一条链。它只用于确认可实现性，以及标出 provider 的盲区；它**不**影响 fixture 的去留。

**3. 负对照的真值**：见 §15.6。

### 15.4 需求 schema（A）

每一项需求都拆成**语义义务**（与 revision 无关）和**按 revision 的实现**。每个锚点字段都是一个按 revision 的槽：

```text
slot:     {revision_A: <realization>, revision_B: <realization>}
realization:
  {state: present, anchor: <anchor>}
  {state: absent,  context: <anchor>}      # absent 不能是空值，必须给出 context

entry:               <slot>
behavior:            <slot>
required_qualifiers: [ <qualifier> ]     # 最多 6 个
rationale:           free text, not scored
```

- anchor 与跳的端点格式相同：`{file, start_line, end_line, expression}`。
- **absent 的 context**（操作性定义，同样要有边界用例并经过裁决）：在 present 的那个 revision 上，这个元素所控制或所供给的那条语句，在 absent 的 revision 上的对应语句。对 guard，是它所保护的语句；对 transform，是第一个读取变换结果的语句；对 entry / behavior，是按 diff 对齐后的对应语句。这使 scorer 能判断 agent 知道缺的是哪里。
- **结构校验**：每一项至少在一个 revision 上是 present；一项在两个 revision 上都 absent 时拒绝提交。
- **qualifier 按 `kind` 使用各自的结构化载荷**。语义字段与 revision 无关；锚点字段都是上面的槽。决定真假的信息必须结构化并参与评分，不能藏在不评分的文字里：

  | kind | 含义 | 语义字段 | 锚点槽 |
  |---|---|---|---|
  | `guard` | 链上某个对象的一个性质，必须成立（或必须不成立），behavior 才会发生 | `expected: must_hold \| must_not_hold` | `subject`（性质所属的对象）、`predicate`（检查或确立这个性质的位置） |
  | `transform` | 链上对值的某个变换，它的有无决定 behavior | `expected: must_be_present \| must_be_absent`（behavior 发生时，这个变换必须存在，或必须不存在；例如缺少清洗是 `must_be_absent`，使路径穿越成为可能的 URL 解码是 `must_be_present`） | `subject`（被变换的值）、`transform`（变换发生的位置） |
  | `config` | 代码路径之外的一个配置值，必须满足某个条件 | `expected_condition: {op: equals \| not_equals \| set \| unset, value: <字面量，op 为 set/unset 时省略>}` | `subject`（读取配置的位置）、`config`（配置项被定义或读出的位置） |
  | `dispatch_target` | 一次动态调用实际到达哪个实现 | — | `call`（调用处）、`target`（到达的实现） |

  - 例如「修复前没有 guard，修复后新增 guard」：`predicate` 的槽在修复前为 `{state: absent, context: <被保护的语句>}`，在修复后为 `{state: present, anchor: <检查>}`。
  - 每个 qualifier 另有一段不评分的 `note`。
  - 真值中，每个 present 的锚点、每个 absent 的 context，都是一个可采集合（逐个裁决）；`config` 的 `value` 也可以列出可采取值的集合（字面量比较，去掉首尾空白）。
- **匹配**（matcher 在看任何 fixture 之前冻结）：
  - 一个槽匹配，当且仅当每个 revision 上的 `state` 相同，并且 present 的 `anchor`（或 absent 的 `context`）落在对应的可采集合中；
  - entry / behavior：槽匹配；
  - qualifier：`kind` 相同，语义字段相同，并且每个锚点槽都匹配。
  - 只有部分 revision 匹配的项，不算匹配；它另作为次要指标报告。
- **闭集之外的需求**：agent 可以提交 `{kind: UNSUPPORTED_REQUIREMENT_TYPE, note}`，每份提交最多 2 个，并且计入 6 个的上限。作者在真值中也可以这样标。见 §15.8 的指标规则。

### 15.5 任务与 A → B → C 的锁定顺序

**任务模板**（在看任何候选之前冻结，只填公告的 CWE 名称和受影响的包名）：

> 评估以下主张：在 `<package>` 中，攻击者可控的输入可能导致 `<CWE name>`。比较提供的 revision_A 与 revision_B，确定为了判断该主张需要证明什么，并最终判断两个 revision 之间的改动与该行为的关系。

- **不给**：commit message、公告正文、CVE / GHSA 编号与标题、函数名、行号、提交日期。
- **revision 名称中性**：revision_A / revision_B 与修复前 / 修复后的对应关系由冻结的种子决定，scorer 再还原。agent 只能通过工具阅读两个 revision 的文件，看不到 git 元数据。
- **A**：
  - agent 只看到任务、需求 schema 与限定条件 `kind` 的定义，**看不到关系词表、provider 支持表，也不能调用核验器**；否则实现能力会反过来提示需求。
  - 需求对象通过结构校验（锚点能解析，`kind` 在闭集内，数量不超过上限）之后，**锁定**成不可变的快照（沿用 §11 的机制）。
- **B**：
  - agent 此时第一次看到关系词表，在 A 锁定的需求之下提出跳。目标是从**自己锁定的** entry 到**自己锁定的** behavior，挂上自己锁定的限定条件，形成每一跳都被核验的链（冻结的 §12 分类器）。
  - 按 revision 分别判定：entry 或 behavior 在某个 revision 上是 absent 时，这个 revision 不要求链；某个限定条件在某个 revision 上是 present 时，这个 revision 的链必须挂上它；absent 时不要求。
  - agent 可以在冻结的工具接口与资源上限内调用冻结的核验器。§15.10 第 6 步要预注册：最大跳数、最大核验调用次数 / 交互轮数、反馈的内容。核验器不返回建议的下一跳、golden 或任何路径提示；`unsupported` 只返回「无法确认」。
  - 需求只读。agent 如果认为 A 错了，可以写一条 `requirement_doubt`，不评分，只报告；**不能修改 A**。B 结束时锁定证据图。
- **C**：
  - 只使用冻结的 A 与 B：不能修改 A 或 B，不能再调用核验器，不能改变证据图。是否还能做普通的代码阅读，在第 6 步决定。
  - agent 对每个 revision 给出主张是否成立。归因按 §1.1 的表推导，与期望的归因比较。
- **失败类别**（分别报告）：
  - A 对、B 对、C 对；
  - A 错，但 C 猜对；
  - A 对，但所需的关系 unsupported（provider 盲区）；
  - A 对，B 有链但漏了限定条件；
  - A 错，导致 B 根本无从实现。

### 15.6 只评 C 的负对照

- **目的**：检查 C 会不会把不成立的主张也判为成立。否则 C 只是在 8 个 `FIX_IMPLICATED` 这一个类别上做测试。
- **生成规则**（在看任何候选之前冻结）：
  - 一个闭合、有序的 CWE 替换表 L：CWE-22 路径穿越、CWE-79 XSS、CWE-89 SQL 注入、CWE-78 OS 命令注入、CWE-287 认证不当、CWE-862 缺少授权、CWE-918 SSRF、CWE-502 反序列化、CWE-601 开放重定向、CWE-611 XXE、CWE-400 资源耗尽、CWE-352 CSRF。
  - 对 CWE 为 c 的 fixture，从 L 中 c 之后的位置开始循环取候选（c 不在 L 中时，从头开始），跳过与 c 同一 CWE 大类的项。
  - 依次取前 3 个候选，交给作者与两个裁决者（§15.1）判断它「在两个 revision 上都不成立」；**第一个三方一致判为不成立**的候选，就成为该 fixture 的负对照主张。能用执行确认的，同时用执行确认。
  - 如果 3 个候选都**没有**得到三方一致的「在两个 revision 上都不成立」，该 fixture 就没有负对照，照实报告。不能看了模型结果再挑容易或难的负例。
  - **不用交换 revision 代替负例**：交换只能产生镜像的归因，不是真正的 `NOT_SUPPORTED`。
- **运行方式**：负对照使用**完全相同**的任务模板与 A → B → C 流程，agent 无法从流程上区分真实主张和负对照。但只有 C 进入负对照的指标，它的 A 与 B 只作描述，不进入 A / B 的主要指标。
- **指标**：负对照的假支持率，即任一 revision 被推导为成立的比例（沿用 §4 的 `negative_control_false_supported_rate`）。
- **局限**：这是一道**弱的**负对照筛查。机械替换出来的主张，有些可能一眼就不成立（例如一个没有数据库的包里的 SQL 注入），因此只能检出「来者不拒」式的失败，不能说明 C 对困难的、似是而非的假主张有多强。不为提高难度引入人工挑选。

### 15.7 unsupported 的处理

- **需求层面**：
  - 真值中的 `UNSUPPORTED_REQUIREMENT_TYPE` 项，不进入按词表计算的 recall，单独作为词表盲区报告；
  - agent 提交的 `UNSUPPORTED_REQUIREMENT_TYPE` 项，单独报告为 **unsupported proposal burden**（每份提交的数量与比例），并受 §15.4 的上限约束，不能用来逃避 precision；
  - RD 期间不临时新增 `kind`。
- **关系层面**：
  - B 中的 `unsupported` 跳永远是 UNVERIFIED；
  - 退出 RD 主要词表的关系（§15.1），它的跳同样视为 unsupported。
  - 如果一条链唯一缺的一步，恰好是参考证据也需要、而核验器表达不了的一步，这条链记为 `PROVIDER_BLIND`：它是结果，不是失败，也不扩展词表。

### 15.8 指标（主要指标只在可采真值上计算）

- **A**：entry、behavior、qualifier 分别计算 recall 与 precision：
  - recall = 被匹配的可采真值项 ÷ 可采真值项（不含真值中的 `UNSUPPORTED_REQUIREMENT_TYPE`）；
  - precision = 匹配上可采真值的提议项 ÷ 提议项（不含 agent 的 `UNSUPPORTED_REQUIREMENT_TYPE`，它们计入 burden）；
  - 匹配到 `INDETERMINATE_TRUTH` 的提议项，从 precision 的分子和分母中都去掉。
- **B**：
  - 已核验的实现：从自己锁定的需求形成 FULL_CHAIN 的 run 所占比例；
  - 正确的已核验实现：FULL_CHAIN，**并且** A 与真值匹配。
  - 「正确的已核验实现」的准确含义是：**在与真值匹配的需求规格之下，得到了一条已核验的链**（verified chain under a truth-matching requirement specification）。B 并不要求核验器证明「不存在」；absent 的正确性来自 A 与真值的匹配，而不是 B 的跳核验器。报告不得暗示 provider 机器证明了缺失。
- **「A 与真值匹配」**的定义：
  - entry 与 behavior 都匹配；
  - 每个可采的限定条件都被匹配；
  - 没有一个提议的限定条件既不匹配可采项、也不匹配 `INDETERMINATE_TRUTH` 项。
- **C**：真实主张上的归因正确率（以执行真值为准）；负对照上的假支持率（§15.6）。
- **限定条件层不可采的 fixture**（§15.1 完整性核对的第二轮仍缺限定条件）：
  - entry 与 behavior 的 recall / precision 照常计算；
  - qualifier 的 recall / precision 记为 `NA`（真值不可采），**不是 0**，不进入合计；
  - B 的「已核验的实现」（从 agent 自己锁定的需求形成 FULL_CHAIN）照常报告；
  - 「正确的已核验实现」记为 `NA`，不进入主指标；
  - §15.5 的失败类别：entry 或 behavior 不匹配时，「A 错」仍可判定，照常归类；entry 与 behavior 都匹配时，「A 对」取决于限定条件，这个 run 记为 `UNCLASSIFIABLE_QUALIFIER_TRUTH`，不塞进任何一类；
  - C 照常计分；
  - 报告列出这类 fixture 的数量，以及受影响的 run 数。
- **另外报告**：
  - §15.5 的失败类别分布；
  - `PROVIDER_BLIND` 的数量，unsupported proposal burden；
  - `INDETERMINATE_TRUTH` 的比例、每个 fixture 的歧义负担，以及敏感性分析（包括把只被一个裁决者指出的缺失项按「必需」计入 recall）；
  - `INCOMPLETE_TRUTH_SPEC` 的发生与修订结果；
  - 只有部分 revision 匹配的需求项；
  - 两个裁决者之间，以及它们与作者之间的一致率（含干扰项上的表现）。
- N 很小，结果以描述为主（附 95% Wilson 区间）。是否设判定门槛，在 §15.10 的第 6 步决定。
- **C 不是一个在四类归因上均衡的基准**：真实主张都来自安全修复，天然偏向 `FIX_IMPLICATED`；负对照只是一道弱筛查。报告不得这样描述 C。

### 15.9 Codex 对草案问题的决定（第 1 轮审查）

- **Q1**：中性的真实主张，另加单独的、只评 C 的负对照（§15.5、§15.6）。
- **Q2**：R016 采用读法 A，写成一般的容器到容器组合定义，并经可判定性检验（§15.1）。
- **Q3**：两个独立的新模型会话；三方一致才可采（§15.1）。
- **Q4**：N = 8（Go、Python 各 4 个），作为第一批研究；窗口的截止时间写成明确的 UTC 时间；使用预留队列（§15.2）。
- **Q5**：B 可以在冻结的上限内调用核验器；A 不可以（§15.5）。
- **第 2 轮**：schema 支持按 revision 的 present / absent；增加真值完整性核对；修正负对照中的逻辑错误；12 类 CWE 替换表作为弱负对照筛查获批。
- **第 3 轮**：缺失项的等价按完整的需求身份（含语义字段与每个 revision 的 state，使用正式 matcher 的规则）判定；限定条件层不可采时，下游依赖完整需求真值的指标与失败类别记为 `NA` / `UNCLASSIFIABLE_QUALIFIER_TRUTH`；同意「第二轮仍缺限定条件时保留 fixture、只放弃其限定条件层」。

### 15.10 顺序（每一步都先经 Codex 审查，再冻结）

1. 本宪法 → 冻结。
2. 操作性定义与边界用例 → 可判定性检验（两个裁决会话）→ 核验器一致性 → 冻结 RD 词表。
3. 选择：下载 OSV 快照并记录 hash → 机械筛选 → 固定种子排序 → 人工可采条件 → 冻结有序可采队列（主用加预留）与拒绝日志。
4. 执行真值 → 需求真值（含干扰项）→ 两个裁决会话 → 完整性核对（必要时修订一次，再由两个新会话重审）→ 必要时替补 → 冻结可采真值与锚点集合。
5. 负对照：按 §15.6 生成候选 → 三方裁决 → 冻结。
6. agent 协议（工具、上限、反馈内容、会话数、执行配置、C 阶段的代码阅读、是否设门槛），并在合成代码上做 plumbing pilot → 冻结。
7. 运行 → 分数在查看细节之前提交 → 报告。

## 变更记录

| 日期 | 修改 | 理由 |
|---|---|---|
| 2026-09-27 | 初稿 | — |
| 2026-09-27 | 改为 protocol v1：只评估 Claude；固定模型、effort 和 CLI 版本；阈值分成 harness 不变量和 agent 门槛两层；真实 fixture 换为 Authlib/Caddy/File Browser；pilot 不计入；新增证据完整率指标；去掉 identity 条件下的「错误归因率」（按定义恒为 0） | 在任何正式 run 之前，与 Codex 讨论后定稿 |
| 2026-09-27 | 补充五条定义性条款，阈值不变：cutoff 措辞改为 knowledge cutoff，不再声称排除了污染；identity 措辞筛查明确为只作诊断；golden 改为按事实和证据集评分，并规定修订规则；新增 run 有效性与重跑规则（§1.2）；新增可追溯性（§1.3）和先冻结分数（§1.4） | 与 Codex 讨论后，在提交锁定之前补充 |
| 2026-09-27 | §2.3 新增模型下线兜底：Haiku 4.5 在阶段 1 完成前下线时改用 Sonnet 5 | Haiku 4.5 的退役承诺只保证到 2026-10-15，避免模型下线逼迫重新预注册 |
| 2026-09-27 | 阶段 2 准备（阶段 1 已完成，尚无任何 Sonnet run）：协议升为 v1.1（runner 加启动预算守卫和按指定 slot 运行；prompt、hypothesis 的传递方式和 11 个 MCP 工具的实现与 v1 相同。执行上下文中的 cwd 在后面一条里有意做了改动，见下方上下文泄露条目）；§3.1 确定 8 个计分 hypothesis，S1 的 T3 改为只留在 truth/、不计分；§3.4 加入必需事实的选取原则和独立审查；新增 §3.5 执行真值（含最小宿主规则，以及执行结果对 S3 标签的修正）；§3.6 预算改为启动上限，固定 gate 和机械裁剪规则；§3.7 门槛见下一条 | 与 Codex 讨论后，在阶段 2 的任何 agent run 之前补充 |
| 2026-09-27 | 根据 Codex 的审查修订，此时尚无任何 Sonnet run：§3.7 改为按**每个真 hypothesis** 分别计算 ≥ 60%，不再按 fixture 合并，否则 H3 这样的单个陷阱失败会被合并后的比例掩盖，这比原来的 fixture 级写法更严格；§3.4 的路径规则改为「依赖保护动作被执行的反证也要证明可达」，golden 在所有 hypothesis 的每一侧都加入路径事实（Authlib：`decode → deserialize_compact → verify`；Caddy：2xx 匹配器 → 挂载 copy 路由 → `HandleResponse`；File Browser：存储路径 → `nameInArchive` → 归档器的 `NameInArchive`）；§3.5 的 S3 执行真值改为真实写出归档再读回条目名；§3.6 按 `agent.jsonl` 发现尝试，gate 校准花费计入所有尝试，增加 STOP 结果，并记录计费方式；case.yaml 中含有答案信息的 notes 移到 golden.yaml，并新增测试，确保 agent 可见的内容里不含 notes、golden、case id 或 CVE 编号 | Codex 审查（REQUEST CHANGES） |
| 2026-09-27 | 发现上下文泄露：agent 的工作目录位于 harness 仓库内，路径里带着 case id 和条件名，而且 Claude Code 会把 git 信息写进系统提示。v1.1 改为使用仓库外的临时空目录，§2.1 新增不变量，§2.4 规定阶段 1 在 v1.1 下复验 | 审查 init 事件时发现 |
| 2026-09-27 | 新增 §8（v2）：v1.1 冻结为失败实验，不重评；v1.2 修复正则错误分类；v2 是只改 prompt 的同期 A/B（forward + swapped，160 个 run，配对分组随机、固定种子），golden 和 scorer 不变，三条成功条件同时满足才算成功 | v1.1 阶段 2 结果出来后，与 Codex 讨论确定 |
| 2026-09-27 | 根据 Codex 对 v2 的审查修订，此时尚无任何 v2 run：runner 改为逐 block 执行，两个组别同时启动、都结束后才进入下一个 block；配对只认严格为 `VALID` 的 run，应有哪些配对以顺序文件为准；新增样本下限（每个单元至少 4/5 个配对，否则判为 `INCONCLUSIVE_INFRA`）；最终判定改为 `INCONCLUSIVE_INFRA` → `HARNESS_INVALID` → `SUCCESS`/`FAIL` 的顺序，统计门槛的结果另记在 `metric_success`；新增测试：treatment 去掉那一句后与 control 逐字节相同、两组共用预算上限、block 屏障、判定的优先顺序 | Codex 审查（REQUEST CHANGES） |
| 2026-09-27 | Codex 第二轮审查（v2 仍无任何 run）：`compare` 在一个有效配对都没有时不再崩溃，直接判为 `INCONCLUSIVE_INFRA`，统计门槛只在样本足够时才计算；上下文泄露不变量扩展为也检查 run 标签、组别和 run 目录（范围是 init 事件和工具返回结果）；§8.3 的「最坏情况」改为准确的说法 | Codex 审查（1 个 blocker，2 个加固点） |
| 2026-09-27 | v2 执行中发现订阅每周额度用尽：从 block 23 起，116 个 run 在约 2 秒内返回 "You've hit your weekly limit"（花费为 0）。CLI 把这个错误报告为 `subtype: success` 且 `is_error: true`，而 `validity.py` 只在 subtype 不是 success 时才检查限额，于是误判成了 VALID。这和 §1.2「rate limit 属于 INFRA_INVALID」不一致，是实现层面的缺陷。**修复发生在产出任何 v2 分数之前**（scorer 在输出前就因为缺少 transcript 崩溃了）：`validity.py` 把额度用尽判为 `INFRA_INVALID: usage_limit`；runner 在 `--order` 模式下，只要某个 block 出现 usage_limit 就停止整批，避免后续 block 空耗重跑次数；scorer 能处理没有 transcript 的 run。agent 能看到的部分（`src/spike/`、两个 prompt、fixture）与 `54b964d` 相同。重新判定结果：44 个 VALID（block 1–22），116 个 INFRA_INVALID（block 23–80）；v1.1 的 240 个 run 不受影响，仍然全部 VALID。额度恢复后，用 `--rerun-invalid` 按同一个顺序文件补跑 block 23–80（第 2 次尝试，每个 block 两组同时启动）。v2 内部的 run 会分属两个 harness commit，差别只在上面这些不影响 agent 的部分 | 执行中发现 |
| 2026-09-28 | 新增 §9（Spike P）：选择 B 方案，v3 降为备用实验；比较 Trailmark 0.5.0 和 CodeQL 2.27.1；只给端点、每种语言一个通用查询、只用默认 flow step；关系类型和表达能力在运行前判定；粒度规则；pilot 只用非评估代码；决策改为按关系类型判定（因为 `guard_property` 事先就判定为表达不了） | v2 结果出来后，与 Codex 讨论确定 |
| 2026-09-28 | 根据 Codex 对 §9 的审查修订，此时还没有任何评估运行：关系状态改为依据事先判定的表达能力来决定，新增 `INCONCLUSIVE_TOOL_FAILURE`，工具故障不再被算作能力不足；按 relation instance 要求同一条路径，禁止把不同路径拼起来算恢复；Authlib 的 106–109 设定 anchor（106、107）；pilot 的通过条件按 provider 分别规定，并新增跨函数调用的 Go pilot；第二档结论改名为 `B_LIMITED_SCOPE_TO_1A`，并写明它不代表完整验收；属性查询不放进基线，留给单独的 P-extension；措辞统一改为「证据路径覆盖了所需的证据位置」 | Codex 审查（REQUEST CHANGES） |
| 2026-09-28 | Codex 第二轮审查（依然没有任何评估运行）：CodeQL 的 call_typed_attribute、registry_dispatch、object_composition、field_flow 四种关系，由非评估的校准 pilot 在查询不改的条件下决定表达能力，不再直接预注册为 ✓，其中 registry_dispatch 属于键控选择；新增端点解析查询，用来区分流程故障和能力结果；pilot 分为 plumbing、calibration、info 三种角色；新增合成 Python 模块；每次 CodeQL 运行都重建工作目录；已安装的 CodeQL 也要核对来源信息；固定「冻结 → 下载 → pilot → 提交校准 → 第二次冻结 → 评估」的顺序 | Codex 审查（2 个 blocker） |
| 2026-09-28 | Codex 第三轮审查（依然没有任何评估运行）：评估时端点解析失败记为 `endpoint_failure`，与工具故障同样处理，不再算作「可表达但没恢复」；校准文件要核对 provider 名称，并确认包含所有待校准的关系；给 pilot 的预期行和端点加上代码片段，并用测试核对是否对得上。Codex 指出的「合成 Python 模块行号整体错了一行」，核实后并不成立：生成的文件第 1 行是一个单独的 `\`，物理行号与 pilot.yaml 一致。但这个写法容易看错，所以把第 1 行换成 docstring，行号保持不变，commit 更新为 `6575bbb`。报告措辞改为「在冻结查询下、经合成 pilot 校准的表达能力」 | Codex 审查（2 个 blocker） |
| 2026-09-28 | 新增 §10（P-Hybrid-1）：provider 逐跳核验，不调用 LLM；跳的格式与真值分离、id 不透明；按关系类型的通用核验器（CodeQL 2.27.1），CONTRADICTED 只来自封闭的形状检查；dev（开发）/ cal（留出校准）/ eval 三个集合；真跳只从 golden 位置切分，假跳按四条规则生成，冻结前人工确认；UNSAFE（含真跳被驳回）、SUPPORTED、PARTIAL、BLIND 四类；按 UNSAFE → 缺口覆盖的顺序路由到 Hybrid-2。registry 核验器在 dev 上加入了通用注册表模型；cal 在第一次运行前追加了同名类属性注册表的对抗用例 | Spike P 之后与 Codex 讨论确定（四点加固） |
| 2026-09-28 | 根据 Codex 对 §10 的审查修订（cal 与 eval 均未运行）：路由改为逐关系判定资格，cal 为 INCONCLUSIVE_TOOL_FAILURE 或缺失的关系不能凭 eval 覆盖进入 Hybrid-2，若唯一有覆盖的缺口因此失格则判为 INCONCLUSIVE_TOOL_FAILURE（补两条路由测试）；真跳测试改为从 golden 按 §10.3 重建链并要求完全一致；score 的 provenance 加入 truth 文件 hash；cal 改称执行留出的校准/挑战集；§10.8 写明负例是相关的挑战用例，指标只描述本集合 | Codex 审查（1 个 blocker；注册表模型、单步组合定义、三态语义、sink 追加规则和 62 跳规模均获批准） |
| 2026-09-29 | 新增 §11（P-Hybrid-2）：共享初稿 → 不可变快照 → 配对分叉（control / 一次性核验反馈）→ 一次修订；形状校验两组共享且锁定前必须通过；反馈白名单；冻结全部关系的核验器输出；golden 与冻结匹配规则；verified / located coverage；盲审（独立的人为 primary，模型为 secondary）；0/0 约定；判定顺序与 Caddy 条件；plumbing pilot 已完成 | P-Hybrid-1 之后与 Codex 讨论确定 |
| 2026-09-29 | 根据 Codex 对 §11 的审查修订（eval 尚未运行）：contradiction 从成功条件中去掉，改为 harness 不变量（锁定的跳在 scorer 中被拒绝即判 HARNESS_INVALID），成功条件剩四条；标签文件必须带 reviewer 身份和盲审声明，并由 scorer 检查；审阅者资格写明：转述者、本轮之前的 Codex 会话和作者都不能担任，secondary 使用全新的 ChatGPT 会话；runner 加入工作树必须干净的检查，并记录 harness commit | Codex 审查（1 个 blocker） |
| 2026-09-29 | 新增 §12.0（草案）：旧基准结束，全部保持原判定；P-Hybrid-3 的问题；设计诊断的规则（C1、C2、G、Q）在第一次运行前提交；Spike P 端点不可表达 | 与 Codex 讨论确定的阶段转换 |
| 2026-09-29 | §12 改为链复现（草案）：同一对象连接器（CodeQL SSA，只输出 SAME_OBJECT / NOT_PROVEN_SAME，dev 与留出的 cal）；没有反馈的描述性复现（3 × 10，与 P-Hybrid-2 初始阶段一致）；规则 G 端点、限定规则、五个分类，从翻转行出发只算 ENTRY_GAP；完整性反馈 A/B 暂缓；真实入口作为独立的 P-extension | Codex 对设计诊断的决定 |
| 2026-09-29 | 根据 Codex 对 §12 的审查修订（尚未冻结）：取消 C1 回退，连接器 cal 成为硬性前置条件，由 runner、eval 输出冻结和 scorer 三处机械执行（cal 为 UNSAFE 判 CONNECTOR_CALIBRATION_FAILED，缺失或不一致判 PROTOCOL_INVALID，cal 只能运行一次）；ENTRY_GAP 改为报告最长的已核验后半段，路径改为真正的节点简单路径；有歧义的节点不参与判定；会话一致性的措辞改得更精确；报告措辞限定为 fully VERIFIED chain | Codex 审查（2 个 blocker） |
| 2026-09-29 | 新增 §13（草案）Completeness Repair：冻结复用 §12；语义契约由通用规则和逐字照录的冻结路径事实陈述组成（与冻结端点一致，已披露为强提示与新接口）；只对初稿不完整的配对分叉，treatment 只多一句话；FULL 判据即冻结分类器；机会抽样（K = 12，M = 30，Authlib 为 N = 5）；离散效应量表；符号检验加各 fixture 方向一致；plumbing pilot 已完成；这条分支到 §13 为止 | Codex 指定这是本分支最后一个行为实验 |
| 2026-09-29 | 根据 Codex 对 §13 的审查修订（尚未冻结）：冻结正式执行配置（与 P-Hybrid-2 的 45 个会话一致：claude-sonnet-5、high、$3.0、1200 秒、CLI 2.1.280），runner 在启动前拒绝不一致的配置，scorer 检查 meta 与实际服务的模型和 CLI 版本，偏差即判 PROTOCOL_INVALID；新增 RUN_INCOMPLETE，与 INCONCLUSIVE_OPPORTUNITY 区分；研究问题严格限定为「在给定由 golden 导出的语义契约的条件下」；约 1% 的误判率注明只针对具体的无效应情形 | Codex 审查（1 个 blocker；契约、K = 12、M = 30、符号检验判据均获批准） |
| 2026-09-29 | 新增 §14（草案）P-extension：四种能力映射为三种跳关系（`def_use`、`argument_binding`、`range_element`；跨函数调用并入 `argument_binding`）；真实入口就是冻结的 Spike P source 端点，§12 局部锚点不变；provider-only，不调用 LLM；dev（已运行，只作参考）/ 留出的 cal / current（95 跳，按 §10.4 规则变异）；Caddy head 由 `def_use` 加冻结的 `object_composition` 接上；局部部分已由 golden 闭合（有测试）；判定顺序为 UNSAFE → INCONCLUSIVE_TOOL_FAILURE → CAPABILITY_GAPS → LOOP_CLOSED；缺口只记录，不新增关系；§14 之后三个当前 fixture 退役 | Codex 的决定（四种能力、真实入口契约、provider-only） |
| 2026-09-29 | 根据 Codex 对 §14 的审查修订（尚未冻结，cal 与 current 均未运行）：判定新增 `CALIBRATION_BLIND`，排在 `CAPABILITY_GAPS` 之前（任一 §14 新核验器在留出的 cal 上为 BLIND 或缺少结果，就不能判为 `LOOP_CLOSED`；PARTIAL 不阻断，不设覆盖比例）；分类单位改为具体的核验器实现（`codeql/语言/关系`，各对应一个查询文件），避免 Go 与 Python 的 `def_use` 合并后掩盖 BLIND；必须具备的核验器清单取自 `relations.yaml`；按关系名的汇总只供报告，判定不读取；§14.2 标题改为「三个 relation，实现四个所需语义步骤」，`argument_binding` 只作为一个复合 relation 报告；语言覆盖写明为不对称、按 fixture 需求决定；负例不因结果修改 | Codex 审查（第 1 轮 1 个 blocker；第 2 轮设计批准，核验器键的层级按 Codex 的建议；复合 relation、Caddy head 的 218 → 233 真值、语言覆盖不对称、PARTIAL 不阻断均获认可） |
| 2026-09-30 | Codex 第 3 轮批准冻结。冻结前按 Codex 给出的执行顺序修改 §14.8：cal 成为 current 的硬性前置条件（cal 出现 UNSAFE、INCONCLUSIVE_TOOL_FAILURE 或 CALIBRATION_BLIND 时，current 不运行，判定只依据 cal），由 `bridge.py` 机械执行（cal 结果存在、没有失败、所用文件 hash 未变）；报告中的按关系汇总标为 report-only aggregate；三个当前 fixture 的退役范围写明 | Codex 审查（APPROVE FREEZE；原文「无论 cal 结果如何 current 都照常运行」与 Codex 给出的顺序不一致，采用更保守的一方） |
| 2026-09-30 | P-Hybrid-2 盲审收尾（尚未计分）：找不到独立的人（操作者声明），按 §11.6 的降级规则，由已完成的全新 ChatGPT 会话审阅作为 primary，报告中标为 model-blind adjudication，没有 secondary，不报告一致率；操作者确认该会话是 Temporary Chat 或 memory 已关闭。发现冻结 scorer 的一个实现缺陷：YAML 1.1 把不加引号的 TRUE / FALSE 解析为布尔值，而 `propose_score.load_review` 只接受字符串，于是任何按说明中示例格式填写的标签文件都会被当作尚未审阅（fail closed，从未产生错误结果）。同类的第二个缺陷：reviewer 块中不加引号的日期被解析为 date 对象，scorer 在写出 JSON 结果时崩溃（写出之前就失败，没有产生任何结果文件）。冻结 scorer 不修改、不重跑旧结果；接收标签文件时把标签和日期显式加引号（序列化兼容，只改语法），并转义 R001 备注中破坏 YAML 的引号，标签和备注的内容都没有改变（已与原始回复逐项核对，文件头有记录）。R030 暴露了 `unsupported` 审阅说明的语义歧义：审阅者把「relation 标得对不对」也纳入了 FALSE 的判断，而不只是「link 是否成立」；标签按冻结流程保留，不作事后修改 | 用户与 Codex 的决定；在计算任何基于该审阅的指标之前记录 |
| 2026-09-30 | 新增 §15（草案）RD 实验宪法：以 R016 为动机的真值可采性流程（操作性定义与边界用例 → 可判定性检验 → 核验器一致性 → 不同家族模型的独立裁决 → 不一致记为 INDETERMINATE_TRUTH，从主要指标中排除并做敏感性分析，附防排除偏倚的规则）；fixture 选择协议（OSV/GHSA 的 Go 与 PyPI 公告、固定日期窗口、机械筛选、固定种子排序、事先列明的人工可采条件与拒绝日志，禁止按 provider 能力入选，排除三个已退役的仓库）；两层真值；需求 schema（qualifier 必须锚定对象与性质，kind 为闭集）；A → B → C 严格锁定；unsupported 的处理；指标；顺序；五个待 Codex 决定的问题。与 §5 的 1A 区分，称为 RD | Codex 的决定：先写实验宪法，再选 fixture |
| 2026-09-30 | 根据 Codex 对 §15 的审查修订（尚未冻结，没有看任何候选）：任务模板改为中性，删去泄露答案的「这个 commit 是修复」，revision 名称中性、由种子映射，不给 commit message 与公告正文；另设只评 C 的负对照（闭合的 CWE 替换表，三方裁决，流程与真实主张完全相同，不用交换 revision 代替）；fixture 替补改为冻结的有序可采队列（每种语言 4 个主用 + 2 个预留，只有 entry / behavior 的 INDETERMINATE_TRUTH 能触发替补，预留用尽就缩小 N，不放宽条件）；qualifier 改为按 kind 的结构化载荷，全部参与匹配。并写定 Codex 的决定：R016 采用读法 A（一般的容器到容器组合定义，同样要经可判定性检验）；两个独立的新模型会话裁决，三方一致才可采；N = 8 作为第一批研究，窗口截止为 2026-09-30T00:00:00Z，并下载 OSV 快照、记录 hash；B 可在冻结上限内调用核验器，A 不能，也看不到关系词表；C 只使用冻结的 A 与 B。另外补充：裁决时混入干扰项，裁决者指出的缺失项记为 INDETERMINATE_TRUTH；可采锚点集合逐个裁决、事先冻结；unsupported proposal burden 与数量上限 | Codex 审查（3 个 blocker；Q1–Q5 已决定） |
| 2026-09-30 | 根据 Codex 对 §15 的第 2 轮审查修订（尚未冻结，没有看任何候选）：需求 schema 改为「语义义务 + 按 revision 的实现」，每个锚点槽在每个 revision 上是 present（给出锚点）或 absent（必须给出 context，其操作性定义同样要经过裁决），matcher 事先冻结；B 按 revision 决定是否要求链与限定条件；增加真值完整性核对：两个裁决者独立指出同一个缺失项（按 kind 与锚点机械判定等价）时，判为 INCOMPLETE_TRUTH_SPEC，作者在 agent 接触前修订一次，再由两个新会话重审该 fixture 的全部需求项；新一轮仍缺 entry / behavior 则替补，仍缺限定条件则该 fixture 的限定条件层不可采；只被一个裁决者指出的缺失项计入歧义负担与敏感性分析；修正负对照「3 个候选都不成立」的逻辑错误；写明 C 不是四类归因上均衡的基准，负对照只是弱筛查；裁决按 fixture 批量进行、审阅表自动生成 | Codex 审查（2 个 blocker 与 1 个文字逻辑错误；其余获批） |
| 2026-09-30 | 根据 Codex 对 §15 的第 3 轮审查修订（尚未冻结，没有看任何候选）：两个裁决者指出的缺失项，只有完整的需求身份相同（kind、全部评分语义字段、每个 revision 的 state、按正式 matcher 规则比较的锚点与 context）才算同一项，语义相反的不合并；格式不合格的缺失项退回同一会话一次只修格式；限定条件层不可采的 fixture：qualifier 的 recall / precision 与「正确的已核验实现」记为 NA，依赖限定条件的「A 对」类 run 记为 UNCLASSIFIABLE_QUALIFIER_TRUTH（entry / behavior 不匹配时「A 错」仍可判定），entry、behavior、B 的自洽实现与 C 照常；明确定义「A 与真值匹配」；「正确的已核验实现」解释为与真值匹配的需求规格之下的已核验链，absent 的正确性来自 A 的匹配而非核验器 | Codex 审查（2 个逻辑问题；其余获批） |
| 2026-10-01 | Codex 第 4 轮批准冻结 §15 宪法（宪法正文不再修改）。记录两条对后续 scorer 实现的要求：`NA` 必须用明确的结构值表示（例如 `null` 加 `status: truth_inadmissible`），不能用 0、空字符串或缺字段；`INDETERMINATE_TRUTH`、`INCOMPLETE_TRUTH_SPEC`、`UNCLASSIFIABLE_QUALIFIER_TRUTH`、`UNSUPPORTED_REQUIREMENT_TYPE` 保持为不同的状态，不合并成一个 unknown | Codex 审查（APPROVE §15 CHARTER FREEZE） |
| 2026-10-01 | §15.10 第 2 步（定义）冻结，经 Codex 两轮审查：`experiments/rd/definitions.yaml` 第 1 版（48 条规则；AB-1 只计调用点实际可达的目标；BE-3 在多处被修改时选唯一的 behavior；QU-1 在 vulnerable revision 上判断、改变包括加上与去掉；QU-2 只排除被选为 behavior 的那一处），合成边界用例 48 个关系用例与 8 个场景的 46 个需求项，作者标签与检查脚本。冻结前补充：每个标签标明 core / boundary（§15.1：core 用例上的争议使关系或类型退出词表，boundary 上的争议使该边界成为 INDETERMINATE），在任何裁决者看到用例之前写定。OSV 快照已备份到用户的 NAS，恢复演练通过 | Codex 审查（APPROVE DEFINITIONS FREEZE） |
| 2026-10-01 | 冻结后、任何裁决者看到用例之前的一处更正：关系用例 r03（`gp-nested-field`，GP-1）的生成代码把表达式与行定位参数写反了，锚点落在外层字段 `Meta: &Meta{Level: 2}` 上；按它的名称与理由（「&Meta{...} 中的键字段」）改为嵌套的 `Level: 2`。标签（TRUE）、tier（core）与 id 都不变；其他带行定位参数的调用逐一核对过，没有同类错误。第 1 轮审阅表（`results/rd-boundary-r1-*`）与机械比较脚本 `decide.py` 在任何裁决之前提交；审阅表不含定义文件开头的注释块（它提到项目文件，并描述作者一侧） | 生成审阅表时发现 |
| 2026-10-01 | 定义可判定性第 1 轮（`cb35bde`，报告 `c8d7971`）：9 个关系组（Go 6 个，Python 3 个）与 entry、behavior、config、dispatch_target，共 13 组全部一致；guard（1/8）与 transform（2/5）在 boundary 用例上有争议，规则都是 QU-1，两个裁决者都判 INDETERMINATE，因为相关性取决于没有指定的触发输入（作者自己的标签在存在量词与全称量词之间不一致）。按 §15.1 第 2 条做唯一一次定义修订，得到 definitions v2（Codex 审查两轮后批准）：`claim` 定义 admissible execution（攻击者控制场景所说的输入，其余状态取代码允许的任意值）；QU-1 改为 claim 层面的必要性，参照事件是在 vulnerable revision 上发生的所主张效果（guard / config / dispatch_target 在每个 admissible execution 中成立；transform 为反事实；修复新增的元素须阻止每一个 admissible execution；排除空洞条件）。不把真值绑定到 agent 看不到的 PoC 输入（Codex 否决了这一提议）。每个场景写明攻击者控制什么。标签按 v2 重新推导，允许改变：q32（s8 新增的 Verified guard）REQUIRED → NOT_REQUIRED；新增 s9（冗余的早期检查，修复前 absent 的 REQUIRED guard q47，以及极性错误的 q48），原有的不透明 id 不变；config 与 dispatch_target 的 4 项按 v2 重新推导，结果不变。第 2 轮重新标注 QU-1 所管的全部 4 个限定条件组（19 项）；关系组、entry 与 behavior 的规则文字未改，不重开。第 2 轮的裁决者（用户选择，冻结在 `results/rd-boundary-r2-judges.json`）：A = 本地 Codex CLI 的 `gpt-6-astra`（medium），B = OpenCode 的 `deepseek/deepseek-flash`（provider 默认 reasoning；Codex 首选 Google 模型，DeepSeek 同样满足非 OpenAI、非 Anthropic 的要求）。第 1 轮是同一家族的两个独立会话，第 2 轮是两个不同的家族。这是唯一一次修订：第 2 轮之后，可判的冻结，不可判的标为 INDETERMINATE，并从主要真值中排除 | Codex 审查（第 2 轮范围修正后批准） |
| 2026-10-01 | 定义可判定性第 2 轮（`f44f466`，报告 `results/rd-boundary-r2.md`）：config、dispatch_target、guard 全部一致，可采；transform 在 core 用例 q27（s7 的 `QueryUnescape` 必须存在）上有争议，按 §15.1 退出 RD 的主要词表。这一判断是最终的，因为 v2 已经是唯一一次修订。裁决者 A（`gpt-6-astra`）指出，v2 让文件系统状态取任意值，经由符号链接的遍历不需要解码，所以解码并非在每个 admissible execution 中都必要；作者与裁决者 B（`deepseek-flash`）都漏掉了这一点。定义层的最终状态：9 个关系组、entry、behavior、guard、config、dispatch_target 可采（关系组还需核验器一致性检查）；transform 退出词表。真值中 transform 类的需求作为词表盲区单独报告，不进入按词表计算的 recall，具体做法在 agent 协议中写定。BE-1、BE-3 中「被修改的变换本身是 behavior」不受影响 | 第 2 轮结果 |
| 2026-10-01 | 更正一处计数错误：关系组是 9 个（Go 6 个，Python 3 个），不是 13 个。第 1 轮共 15 组，其中 13 组一致、2 组有争议；此前的报告、变更记录与给用户和 Codex 的说明中，「13 个关系组」「17/19 组」都是误写，结论不变。由核验器一致性检查的测试发现 | 测试发现 |
| 2026-10-01 | 冻结核验器一致性检查（§15.1 第 3 条；`experiments/rd/conformance.py`），经 Codex 三轮审查：单位是具体的核验器实现（`codeql/<语言>/<关系>`）；真 → UNVERIFIED 是 provider 盲区，假 → VERIFIED 或真 → CONTRADICTED 是与定义冲突；UNSAFE → NON_CONFORMANT（该语言的这个核验器退出 provider 支持词表，它的结论永远不作为 VERIFIED 的证据；关系定义保留在真值词表中，其他语言不受影响）；BLIND → UNSUPPORTED；必须具备的 9 个核验器由冻结的真值词表生成，表中缺失或多出、缺少真或假用例、覆盖不完整，都是 PROTOCOL_INVALID；gate 为 READY、INCONCLUSIVE_TOOL_FAILURE 或 PROTOCOL_INVALID，只有 READY 时候选选择才能读取 OSV 快照；只有第 1 次出现工具故障时，才允许一次基础设施重跑，只重跑失败的 fixture，并且必须与第 1 次的 harness commit、CodeQL 版本、全部仪器文件 hash 完全一致（两次之间不提交任何东西），没有第 3 次；B 阶段规则：SUPPORTED / PARTIAL 的组合可以机器核验；UNSUPPORTED / NON_CONFORMANT 的组合，agent 可以提出，但只标为 unsupported / unverified；agent 只知道某个组合能否核验。不为这次检查修改任何查询 | Codex 审查（批准冻结） |
| 2026-10-01 | 核验器一致性检查完成（`0f7e0b1`，报告 `results/rd-conformance.md`）：gate READY；一次尝试，没有工具故障；7 个核验器 SUPPORTED，`codeql/go/argument_binding`（接口分派、函数值）与 `codeql/go/object_composition`（指针别名）为 PARTIAL；没有任何假用例被判为 VERIFIED，也没有核验器与定义冲突。§15.10 第 2 步（定义与真值基础设施）到此结束 | 一致性检查结果 |
| 2026-10-01 | 冻结 fixture 选择脚本（§15.2；`experiments/rd/selection.py`），经 Codex 三轮审查：唯一读取快照的入口先检查一致性 gate 并核对快照 hash；只看公告的机械筛选（生态、窗口、撤回、恰好一个可定位的修复 commit（GitHub `owner/repo` 或 GitLab 嵌套命名空间；PR 不算）、退役仓库），按（仓库, commit）去重并合并别名、CWE 与来源生态，每种语言用种子 20261002 打乱；需要 diff 的机械筛选按顺序惰性执行（修复 commit 必须恰好有一个父 commit；改动了该语言的非测试源文件；去掉测试后改动不超过 200 行）；服务器明确回答不存在（冻结的 4 个模式）判 COMMIT_UNAVAILABLE，其余抓取失败是基础设施：候选保持待定，3 次后整个选择停止（INCONCLUSIVE_INFRA），不扩充模式表；人工判定取冻结的枚举，审阅边界内依次尝试 TEST → POC → PROBE（60 分钟），否则判 REVIEW_BOUNDARY_REACHED；队列：每种语言 4 个主用 + 2 个预留，同一仓库只取一个，一个候选占它所属每个 CWE 大类的名额、每类最多 2 个（整个队列计），两种语言按位置轮流先选（先选者由种子决定）；`pool` 之后脚本、池与哈希链日志都不能变（SELECTION_PROTOCOL_CHANGED）；不读取 provider 支持表 | Codex 审查（批准选择冻结） |
| 2026-10-02 | 冻结后 harness wiring defect correction（HC-1，经 Codex 批准「complete HC-1 in one shot」）：C.1 冻结的 matcher（node-ref + 列跨度输入）与冻结的 anchor schema（`{file,start_line,end_line,expression}`）在 C.1–C.3 前各自冻结，技术上无法互相调用；补齐 `experiments/rd/truth/resolver.py`（严格唯一整行定位，仅容忍缩进、内部文本精确，frozen matcher 独占 identity 决定，`resolve_doc` 预解析使 `agreement.py` 不改即可运行）、`anchor_machinery.py`（distractors 所需的通用 near-move/context/present/rebuild callbacks）、`revision_map.py`（author truth 用 canonical vuln/fixed，按 `sha256(seed:fixture_id)` 一次性映射到 outward revision_A/B 并拒绝二次 remap，seed 绑定冻结 pool provenance，source provider 按映射角色取源以防标签/源码错位）；`truth-tooling-freeze.json` 新增 `selection`（pool_sha256+seed）并把 `freeze.py` 自身纳入 `TOOL_SOURCES`。**no measurement semantics changed; previously frozen anchor schema and matcher were technically disconnected.** 全套 synthetic tests 249 passed, 0 xfailed。约定：这是冻结后最后一笔 infra debt，此后 fresh fixture 的表达困难一律记作实验结果，不再回基础设施层修（纯实现 bug 除外） | Codex 审查（REQUEST CHANGES → 四项补齐后批准） |
| 2026-10-02 | RD C.4 第 1 个 fixture（SiYuan `GHSA-fq2j-j8hc-8vw8`，Go #1）truth 冻结：按冻结 §15.1 做三方裁决（作者 + 两个全新隔离 judge：A=gpt-6-astra/Codex CLI，B=deepseek-flash/OpenCode `--standalone`，各跑一次，tools 关闭，逐字相同 bundle，judge 只拿 vuln/fixed 标注；agent-facing seed A/B 不用于裁决）。机械 reconciliation（`agreement.check`，opaque→real 经 sheet-key）结果三方一致：`entry = localPath := n.TokensStr()`（两 revision present）与 `behavior = 新增 IsSensitivePath guard`（fixed present / vuln absent，context=它守护的 copy site）均可采；6 个 distractor（near-move / state-flip）两 judge 全判 NOT_REQUIRED；无 indeterminate / distractor-conflict / missing，fixture 可采，不触发 reserve。route auth（CheckAdminRole/CheckReadonly）与 `/etc` 去重按 QU-1 记为非评分 note（不是 requirement、也不是 UNSUPPORTED_REQUIREMENT_TYPE）。judge bundle 的 advisory 证据机械剥离 fix-attribution（原文入 author-side redaction log，不进 bundle）。冻结物：`experiments/rd/truth/fixtures/GHSA-fq2j-j8hc-8vw8/`（requirement-truth / executable-truth / judge-bundle / judge-a,b / sheet-key / reconciliation）。下一个：Vikunja（Go #2） | 两个 fresh judge 三方一致 → freeze |
| 2026-10-03 | RD C.4 第 2 个 fixture（Vikunja `GHSA-mr3j-p26x-72x4`，Go #2，access-control/IDOR）truth 冻结：同 §15.1 三方裁决（作者 + gpt-6-astra/Codex CLI + deepseek-flash/OpenCode `--standalone`，各一次，tools 关，逐字相同 bundle，vuln/fixed 标注）。机械 reconciliation 三方一致：`entry = TaskComment.ReadOne 的请求绑定 receiver`（EN-1，missing-auth → 请求参数；两 revision present，签名 vuln L228 / fixed L229）与 `behavior = getTaskCommentSimple 新增的 .And("task_id = ?", tc.TaskID) 约束`（BE-1；fixed present / vuln absent，context AC-3 diff-aligned `NoAutoCondition().`）均可采；6 个 distractor 全判 NOT_REQUIRED；无 indeterminate/conflict/missing，不触发 reserve。单行修复无 qualifier。advisory 证据 0 行 fix-attribution。冻结物：`experiments/rd/truth/fixtures/GHSA-mr3j-p26x-72x4/`。下一个：DHCP（Go #3） | 两个 fresh judge 三方一致 → freeze |
| 2026-10-03 | RD C.4 第 3 个冻结 fixture（DHCP `GO-2026-6237`，go-primary 队列 #4，panic/DoS via short IPv4 frame）truth 冻结：§15.1 三方裁决（作者 + gpt-6-astra + deepseek-flash，各一次，隔离，逐字 bundle，vuln/fixed）。三方一致：`entry = upc.PacketConn.ReadFrom(pkt)`（两 revision present，L92）与 `behavior = 新增 if ipPayloadLen < udpHdrLen { continue } 守卫`（BE-1/BE-3，fixed L118 present / vuln absent，context AC-3 `if !buf.Has(udpHdrLen) {` L114）均可采；6 distractor 全 NOT_REQUIRED；无 indeterminate/conflict/missing。第二处新增 buf.Has(dhcpLen) 检查按 BE-3 记为非评分 note。**流程说明**：此 fixture（队列 #4）在 flagd（#3）之前被 authoring+adjudication，属队列顺序 slip；无正确性影响（各 fixture 独立、judge 隔离、reserve 替补与顺序无关、已审 primary 全可采），操作者批准照常冻结，flagd(#3) 随后补审。advisory 证据为事实、0 fix-attribution 行。冻结物：`experiments/rd/truth/fixtures/GO-2026-6237/` | 两 judge 三方一致 → freeze（顺序 slip 已记录） |
| 2026-10-03 | RD C.4：flagd（`GHSA-rmrf-g9r3-73pm`，go-primary #3，resource-consumption）判为**不可采**——requirement behavior 在 §15.3 BE-3 下为 INDETERMINATE_TRUTH：修复把同一 body-size 强制（`http.MaxBytesHandler(h, MaxRequestBodyBytes)`）加在两个相互独立的 service-setup 分支（OFREP service → 413；connect service → 429），属「不同分支各自决定效果、无法排序」情形。按 §15.1 不可采，§15.2 取下一个 Go reserve = **oh-my-posh（`GHSA-fwjx-9p69-h25h`，CWE-150，reserve #6）**；CWE 配额复核通过（per_cwe_class≤2），新 go-primary 集合 = SiYuan/Vikunja/DHCP/oh-my-posh。与之前 supplemental 确认不矛盾：那是 executable-truth 的 flip（真实），此处 INDETERMINATE 的是 requirement behavior 锚点（两分支）。冻结 selection 队列不改（append-only），此替补为 truth 阶段事件，记录于 `experiments/rd/truth/fixtures/GHSA-rmrf-g9r3-73pm/inadmissible.md`。未对 flagd 起 judge（无单一 behavior 可判）。操作者批准 | BE-3 INDETERMINATE → §15.2 替补 |
| 2026-10-03 | RD C.4：oh-my-posh（`GHSA-fwjx-9p69-h25h`，flagd 的 §15.2 替补，CWE-150）经三方裁决判为**不可采**——behavior（新增 `if isControlRune(s) { return }`）三方一致可采，但 **entry（`func write(s rune)`，EN-1）INDETERMINATE**：作者 + Judge B 判 REQUIRED，Judge A 判 INDETERMINATE（三方不一致，`agreement.check`）。按 §15.1「entry 或 behavior 为 INDETERMINATE 即不可采」，且 label 三方分歧无作者 re-anchor 步骤（锚点集事先冻结、本项只给一个锚），故不可采。§15.2 取下一个 Go reserve = **fabric-ca（`GHSA-xghw-p77p-3r7x`，injection，#7）**；配额复核通过，新 go-primary 集合 = SiYuan/Vikunja/DHCP/fabric-ca；**Go reserve 就此用尽**（若 fabric-ca 再不可采则缩小 N）。这是第 2 个 Go 替补（flagd behavior-INDETERMINATE；oh-my-posh entry-INDETERMINATE）。executable-truth flip 仍真实，不可采仅关 §15.3 requirement truth。操作者批准。记录于 `experiments/rd/truth/fixtures/GHSA-fwjx-9p69-h25h/reconciliation.md` | 三方分歧（entry INDETERMINATE）→ §15.2 替补 |
| 2026-10-03 | RD C.4：fabric-ca（`GHSA-xghw-p77p-3r7x`，oh-my-posh 的 §15.2 替补，LDAP injection）经三方裁决判为**不可采**——entry（`Client.GetUser` 的 username 参数，EN-1）三方一致可采，但 **behavior INDETERMINATE**：Judge B REQUIRED、作者 REQUIRED、**Judge A NOT_REQUIRED** 并提单侧 missing（同一 `EscapeFilter` fixed 锚点，但 vuln context 应锚在语句 `sreq := ldap.NewSearchRequest(` 而非作者所锚的子表达式 `fmt.Sprintf(lc.UserFilter, username),`；AC-2 要求"首个读取被转换值的语句"，Judge A 正确）。按冻结规则 judge 看过后 author truth 不改（不开"judge 揭答案→改 truth→重交"的口子），故 behavior INDETERMINATE、fixture 不可采。§15.2 Go reserve 已用尽（oh-my-posh、fabric-ca 两个 reserve 均不可采）→ **Go tranche 缩为 N=3**（SiYuan/Vikunja/DHCP），不回填（不重筛、不启用 quota-skipped、不开第三 reserve）。两个 reserve 失败**均为作者锚点粒度错误**（非 fixture/verifier 失败），诚实记录。Codex 选 (a)：不改 charter、不加事后锚点更正例外；Python 前把"语句粒度 anchor 自审"（`experiments/rd/truth/ANCHOR-SELF-REVIEW.md`）固定为 authoring discipline（非协议修改），且自审只在首次 judge 前进行。更正：fixture tranche 的 judge 模型为 gpt-6.1-sol(A)/deepseek-flash(B)（此前记为 gpt-6-astra，源自 boundary 轮配置；内容不受影响）| Codex 选 (a)；§15.2 缩 N | 
| 2026-10-03 | RD C.4 Python 第 1 个 fixture（LiteLLM `GHSA-hx8v-g79f-8w5f`，CWE-918 SSRF）truth 冻结：按 `ANCHOR-SELF-REVIEW.md` 在 judge 前逐项自检并记录 prompt/bundle hash；entry 采用 EN-2 的精确语句锚点 `router_config = data.pop("user_config")`（两 revision present），避免 handoff 候选 `is_request_body_safe.request_body` 因整行 resolver 只能落到 `FunctionDef` 的粗粒度错误；behavior 为 BE-1 changed check `banned_params` assignment（vuln `["api_base", "base_url"]` / fixed 加入 `"user_config"`，两 revision present）。作者 + 两个 fresh isolated judge（A=`gpt-6.1-sol`，B=`deepseek-flash`）三方一致，两真实项均 REQUIRED，6 distractor 均 NOT_REQUIRED，无 indeterminate/conflict/missing/ambiguity burden；fixture 可采，不触发 reserve。首次沙箱 judge 调用属基础设施失败且未产出标签；以绝对 fixture 路径和一次性网络/日志权限启动全新会话成功，同一冻结 prompt 未变。冻结物：`experiments/rd/truth/fixtures/GHSA-hx8v-g79f-8w5f/`。下一个：Reflex `PYSEC-2026-1868`（Python #2） | 两个 fresh judge 三方一致 → freeze |
| 2026-10-03 | RD C.4：Reflex（`PYSEC-2026-1868`，Python primary #2，open redirect）判为**不可采**——执行真值仍成立（同一生成脚本与输入：vuln 自动跳到任意外部 URL，fixed 不跳转并保留合法 Codespaces 跨端口流程），但 entry 与 behavior 位于 Python 多行 f-string 内嵌的 JavaScript 中；冻结 CPython-AST matcher 将 `params.get("redirect_to")`、两个新增 hostname guard、`a.href` 与 `a.click()` 在各自 revision 内全部解析为同一个 `Constant` 节点，无法区分 EN/BE 精确语句或生成不同身份的近邻 distractor。按 `ANCHOR-SELF-REVIEW.md` 不允许用包含目标文本的整段字符串冒充语句锚点；这是冻结 harness 下的可表达性测量结果，不改 resolver/matcher。entry/behavior truth 因而为 INDETERMINATE，fixture 按 §15.1 不可采；未启动 judge。§15.2 提升首个 Python reserve **Mnemosyne（`GHSA-xcw4-53cc-hv32`，cryptography，#21）**，CWE 配额复核通过；冻结 selection 队列与日志不改。记录于 `experiments/rd/truth/fixtures/PYSEC-2026-1868/inadmissible.md` | anchor identity 不可表达 → §15.2 替补 |
| 2026-10-03 | RD C.4 Python 第 2 个冻结 fixture（Mnemosyne `GHSA-xcw4-53cc-hv32`，Reflex 的 §15.2 替补，CWE-347）truth 冻结：触发输入限定为格式正确、`alg: HS256`、未来过期时间但签名伪造的 bearer JWT；entry 为 JWT 分支读取 `Authorization` 的赋值（EN-2，两 revision present），behavior 为新增 `if not valid_signature:` 守卫（BE-1/BE-3，fixed present / vuln absent，AC-1 context 为对应的 `exp = payload.get("exp", 0)`）。格式、类型、算法和过期校验不决定该窄触发输入，记为同 commit 非评分 hardening；JWT secret 与网络可达性固定在 scenario，不另作 qualifier。作者自审、resolver、prompt/bundle hash 均在 judge 前冻结；A=`gpt-6.1-sol`、B=`deepseek-flash` 两个 fresh isolated judge 与作者三方一致：两真实项 REQUIRED，6 distractor 全 NOT_REQUIRED，无 indeterminate/conflict/missing/ambiguity burden。Mnemosyne 成为 Python frozen #2，不再触发替补。冻结物：`experiments/rd/truth/fixtures/GHSA-xcw4-53cc-hv32/`。下一个：llama-stack `GHSA-xmfj-7pp5-fxr6`（Python primary #3） | 两个 fresh judge 三方一致 → freeze |
| 2026-10-03 | RD C.4：llama-stack（`GHSA-xmfj-7pp5-fxr6`，Python primary #3，CWE-532）判为**不可采**——PROBE 的执行 flip 真实（vuln 初始化日志含真实 PGVector 密码，fixed 以 `******` 遮盖），新增 `safe_config` 变换及其 AC-2 日志 context 也可精确表达；但冻结 claim/EN 语义要求 attacker-controlled triggering input，而被泄露的密码是部署者秘密、攻击者只是日志观察者。把密码说成攻击者控制会使泄露主张失去意义；Pydantic 的实际字段赋值又无仓库源语句。两个自然 config 参数候选被冻结 resolver 分别解析成整个 `AsyncFunctionDef` / `FunctionDef`，不能冒充精确参数；字段声明不是运行时输入定义，`self.config = config` 是 EN-3 后续存储。因此 entry = INDETERMINATE_TRUTH，未构建 bundle、未启动 judge、不改 definitions/matcher/resolver。§15.2 提升最后一个 Python reserve **Flask-Reuploaded（`GHSA-937x-gpqr-72gg`，CWE-178/CWE-434，#22）**，配额通过；Python reserve 至此用尽，后续失败即缩 N、不回填。记录于 `experiments/rd/truth/fixtures/GHSA-xmfj-7pp5-fxr6/inadmissible.md` | claim/entry 语义与精确锚点不可表达 → §15.2 最后替补 |
| 2026-10-03 | RD C.4：Flask-Reuploaded（`GHSA-937x-gpqr-72gg`，llama-stack 的最后一个 §15.2 替补，CWE-178/CWE-434）判为**不可采**——TEST 执行 flip 真实（`name="backdoor.PHP"` 在 vuln 绕过 `AllExcept(SCRIPTS)`，fixed 抛 `UploadNotAllowed`，fixed 全文件 52 passed）；behavior 也可精确表达为新增 `basename = lowercase_ext(basename)` 变换（BE-1，fixed present / vuln absent，AC-2 context=`ext = extension(basename)`）。但 EN-1 要求精确 `UploadSet.save` 的 `name` 参数；冻结 whole-line resolver 对 `name: str | None = None` 与 `def save(` 都解析成整个 `FunctionDef`，不能用函数粗锚点冒充参数。`name = secure_filename(name)` 与 `basename = name` 虽是可解析 `Assign`，均属 EN-3 后续派生值。故 entry = INDETERMINATE_TRUTH，未构建 bundle、未启动 judge。Python 两个 reserve 均已消费（Mnemosyne 可采、Flask-Reuploaded 不可采）→ tranche 从目标 N=4 缩为最多 N=3，不回填；继续审剩余 AGiXT primary，若通过则 Python N=3，否则 N=2。记录于 `experiments/rd/truth/fixtures/GHSA-937x-gpqr-72gg/inadmissible.md` | 精确参数锚点不可表达；reserves exhausted → 缩 N |
| 2026-10-03 | RD C.4：AGiXT（`GHSA-5gfj-64gh-mgmw`，最后一个 Python primary，CWE-22）判为**不可采**——PROBE 执行 flip 真实（`safe_join("../<sibling>/probe.txt")` 在 vuln 返回并创建 workspace 外路径，fixed 抛 `PermissionError`；inside control 两版正常）；behavior 可按 BE-3 精确表达为最后的 containment `if`（fixed present / vuln absent，AC-1 context=`path_dir = os.path.dirname(new_path)`），前面的 realpath 变换只喂给该直接决定检查。但 entry 无精确锚点：endpoint 的 `command` 参数解析成整个 `AsyncFunctionDef`；公告标作 source 的当前 `command_args=command.command_args` 是多行调用的一部分并解析成整个 `Call`，不是提取赋值；`read_file.filename` 与 `safe_join.paths` 也落到整个函数；Pydantic 字段声明不是运行时入口，后续值受 EN-3 排除。故 entry = INDETERMINATE_TRUTH，未构建 bundle、未启动 judge。Python reserves 已耗尽，不回填，Python **CLOSED at N=2**（LiteLLM、Mnemosyne）；与 Go N=3 合计，RD C.4 从计划 N=8 实现为 **N=5**。记录于 `experiments/rd/truth/fixtures/GHSA-5gfj-64gh-mgmw/inadmissible.md` | 精确 entry 不可表达；reserves exhausted → Python N=2、总 N=5 |
| 2026-10-03 | RD §15.10 step 4（C.4 fixture truth）完成并汇总于 `experiments/rd/truth/C4-REPORT.md`：计划 Go/Python 各 4（N=8），最终 Go N=3、Python N=2、合计 **N=5**。5 个可采 fixture 的 10 个核心项均为作者+A+B 三方 REQUIRED，30 个 distractor 均被两 judge 判 NOT_REQUIRED，无 missing；7 个不可采尝试逐项保留原因。全过程未修改冻结 charter/tooling、未在 judge 后改 author truth、未扩 reserve、未回填。下一步为 §15.6 负对照生成与三方裁决 | step 4 complete；planned 8 → realized 5 |
| 2026-10-03 | RD §15.10 step 5 的执行合同与候选清单在任何负对照作者标签/judge run 前冻结：`negative-controls/PROCEDURE.md` 只操作化既有 §15.6，不改候选生成或测量语义；5 个可采 fixture 各按冻结 `negative_control.py` 生成有序 3 候选并批量独立标注两 revision。标签为 SUPPORTED / NOT_SUPPORTED / INDETERMINATE；只有作者+A+B 对同一候选的 vuln/fixed 均一致 NOT_SUPPORTED 才合格，取冻结顺序第一个，否则该 fixture 无负对照。证据不足必须 INDETERMINATE，源码 regex inventory 只是诊断、不得把“未搜到”自动当不存在。固定候选见 `negative-controls/manifest.yaml` | step 5 operational freeze before adjudication |
| 2026-10-03 | RD §15.6 负对照第 1 个裁决完成（DHCP `GO-2026-6237`）：作者标签与 prompt 先以 `008f95d` 提交冻结，再由 fresh isolated A=`gpt-6.1-sol`、B=`deepseek-flash` 读取逐字相同 prompt。candidate-01 CWE-352 在两 revision 上获三方一致 NOT_SUPPORTED；candidate-02 CWE-22 因 A 两格 INDETERMINATE 不合格；candidate-03 CWE-79 也获三方一致 NOT_SUPPORTED。按冻结顺序机械选择首个合格项，故本 fixture 负对照为 **CWE-352 CSRF**；未重跑、未改标签。结构校验通过，raw transcripts 保留于 `negative-controls/GO-2026-6237/` | three-way negative control selected |
| 2026-10-03 | RD §15.6 负对照第 2 个裁决完成（Mnemosyne `GHSA-xcw4-53cc-hv32`）：author/prompt 先以 `461e3b6` 冻结；A=`gpt-6.1-sol`、B=`deepseek-flash` 与作者六格完全一致。CWE-22（HTTP `bank`→未约束 DB path）和 CWE-79（query/memory→未转义 HTML）两版均 SUPPORTED；CWE-89 因 3.6 万行 package 面与 1044 条宽匹配无法据给定证据证明存在或不存在，两版均 INDETERMINATE。没有候选满足六格全 NOT_SUPPORTED，故本 fixture **无负对照**；未重跑、未改标签 | three-way agreement; no qualifying negative control |
| 2026-10-03 | RD §15.6 负对照第 3 个裁决完成（SiYuan `GHSA-fq2j-j8hc-8vw8`）：author/prompt 先以 `7ed8539` 冻结；A=`gpt-6.1-sol`、B=`deepseek-flash` 与作者六格完全一致。CWE-22 在 vuln 由已复现的绝对路径文件泄露支持，fixed 修复该触发但 9.5 万行产品面不足以证明包级不存在，故 SUPPORTED/INDETERMINATE；CWE-79 与 CWE-89 因大量 HTML/SQL 表面但无充分存在或不存在证据，两版均 INDETERMINATE。没有六格全 NOT_SUPPORTED 候选，故本 fixture **无负对照**；未重跑、未改标签 | three-way agreement; no qualifying negative control |
| 2026-10-03 | RD §15.6 负对照第 4 个裁决完成（Vikunja `GHSA-mr3j-p26x-72x4`）：author/prompt 先以 `8631754` 冻结；CWE-918 三方均判两版 INDETERMINATE。对 CWE-502 与 CWE-601，作者和 B=`deepseek-flash` 判两版 NOT_SUPPORTED，但 A=`gpt-6.1-sol` 对四格均判 INDETERMINATE，认为 7.5 万行包级不存在证据仍非决定性。按冻结规则不补证、不改标签、不重跑，故没有六格全 NOT_SUPPORTED 候选，本 fixture **无负对照** | Judge A conservatism prevents qualification; no rerun |
| 2026-10-03 | RD §15.6 负对照第 5 个裁决完成（LiteLLM Proxy `GHSA-hx8v-g79f-8w5f`）：author/prompt 先以 `943b14e` 冻结；CWE-601 三方均判两版 SUPPORTED。对 CWE-502 与 CWE-611，作者和 B=`deepseek-flash` 判两版 NOT_SUPPORTED，但 A=`gpt-6.1-sol` 对四格均判 INDETERMINATE，认为 19.4 万行包级不存在证据仍非决定性。按冻结规则不补证、不改标签、不重跑，故没有六格全 NOT_SUPPORTED 候选，本 fixture **无负对照** | Judge A conservatism prevents qualification; no rerun |
| 2026-10-03 | RD §15.10 step 5（§15.6 负对照）完成并汇总于 `experiments/rd/truth/negative-controls/REPORT.md`：5 个冻结 fixture 均到达终态，只有 DHCP candidate-01 **CWE-352 CSRF** 获作者+A+B 两 revision 全部 NOT_SUPPORTED，成为唯一可用负对照（N=1）；SiYuan、Vikunja、LiteLLM 均无合格候选。追溯审计发现 Mnemosyne 的冻结 manifest 范围为 “Mnemosyne sync server”，但其 prompt 错误扩大到整个 `mnemosyne-memory` distribution；因 judge 已见 prompt，按不可变规则不改、不重跑，该批次保留为审计物但标为 scope-invalid，不进入负对照选择或下游分母。它原始结果本就未选择候选，故不污染唯一选中项。下一步为 agent protocol + synthetic plumbing pilot | step 5 complete；usable negative controls N=1；Mnemosyne scope deviation quarantined |
| 2026-10-03 | RD §15.10 step 6 agent 协议冻结：6 个不透明 task（5 real + DHCP/CWE-352 negative control）按 seed-20261003 固定顺序，每 task 一个 fresh `claude-sonnet-5`/high 会话顺序 resume A→B→C；A/B/C 增量预算 $3/$3/$1、累计 CLI cap $3/$6/$7、timeout 1200/1800/600 秒，总 launch ceiling $42；A/B 共享中性只读源码面，A 不见关系/provider，B 最多 18 次 closed-feedback check、12 个 checked hops，C 只见 sealed A/B 且无代码/verifier 工具；无行为成功门槛。补做了 §15.3 明定但 step 4 遗漏的 pre-agent reference audit：SiYuan/Vikunja/DHCP/Mnemosyne 均为 `PROVIDER_BLIND`；LiteLLM 的冻结 behavior safety check 先于冻结 entry extraction，故正向语义链为 `REFERENCE_UNREALIZABLE`。按冻结规则不改 judge-seen truth、不替补、不扩词表；所有 5 个仍进入 A/C 与主 B 分母，另报 reference-realizable B 子集。合成 Claude pilot attempt 1 的 A/B/C 功能均通过，但审计发现 resumed session 成本为累计值；正式 run 前修为增量预算+累计 cap、每会话累计成本只计一次，并保留 attempt 1。修复后 attempt 2 再次三阶段 `VALID/locked`，同一 served session、精确工具面、空 memory、模型/CLI/cap 均通过；随后全仓导入顺序审计发现旧实验同名 `run.py`/`freeze.py` 可污染测试进程，改为绝对路径专属模块加载并新增身份断言。attempt 3 因 synthetic source 字节变化后错误复用旧 commit analysis，B 的 MCP 在暴露工具前失败；修复 pilot analysis provenance 校验，并把“零交互且缺少预期工具面”明确判为 `INFRA_INVALID`。attempt 4 是该基础设施失败的重试与 freeze 所认最终 pilot；没有任何 measured run。冻结同时覆盖在线/离线 provider gate 一致性、缺失任务分母与实际 served model/tool surface 的 fail-closed 回归测试 | step 6 operational freeze before measured runs；late reference audit + post-repair pilot |
| 2026-10-03 | RD 正式 v1 首次启动被错误放入 DNS 受限沙箱：task-03 三次均在零 token、零费用、零可用工具交互前以 API `EAI_AGAIN` 失败；为诊断共同故障，操作者中断了刚启动的 task-04。没有模型产出评估内容。按冻结规则不删除/清零失败 attempt，先由冻结 scorer 生成 `HARNESS_INVALID`，并在查看 transcript 前以 `6241243` 提交。随后建立 **RD v2**，不改变任务顺序、prompt、truth、agent 工具/反馈、会话结构、模型/CLI、预算/timeout、scorer 或 $42 measured ceiling；只在创建 measured attempt 前增加三项无模型 gate（本地登录、Anthropic 端点连通、同一动态 stdio MCP 握手+精确 A 工具面），并让明确 API error 优先于泛化的空工具面原因。v1 结果成为 v2 freeze 输入；v2 复用已通过的 v1 synthetic pilot，因为 measured intervention 未变，并以 deterministic tests 覆盖新 gate | v1 administrative launch retained as invalid；v2 recovery before any usable measured interaction |
| 2026-10-03 | RD v3 one-shot held-out batch 由独立无上下文 curator 按冻结 contract 生成（20 A + 3 provider；aggregate `10b696811d8529459d428fa702fb23e2a4efcb4e04e7cfb263628f783a4cd97f`）并原样提交为 `d2f655e`。冻结 validator 在任何模型/provider 调用前拒绝 `go-claim-specific-entry-02` 的 behavior anchor `queue <- canonicalTopic`：该完整 Go send statement 解析为 `*ast.SendStmt`，但冻结 construction whitelist 仅接受 Assign/Return/If；公开 curator contract/schema 未枚举这一更窄集合。终态以 `906442d` 记录为 **`CALIBRATION_INVALID`**，Claude sessions=0、provider challenges=0、formal tasks=0、支出/overshoot=`$0/$0`。按 §v3 one-shot 终止规则不修 case、不重发 batch、不启动 fresh selection/formal、不开 v4；结果发布于 `results/rd-agent-v3.{json,md}`，项目关闭。此结果不测量 v3 treatment，RD v2 仍是最后一份有效 agent 测量 | public contract/validator mismatch caught fail-closed；project closed |
