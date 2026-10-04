# Spike P 报告：provider 能否提供可达性证据（定向查询）

- 第一次冻结 `7702441` → 下载 CodeQL 2.27.1（sha256 校验通过）→ pilot 校准 → 第二次冻结 `9bb01a0` → 评估（只跑了一次）→ 分数冻结 `f8a7382`（`spike-p-reach.json`）。
- 所有运行都正常完成。每个 fixture、每一侧的 CodeQL 端点都解析到了节点（source 1 个，sink 1–2 个）。没有工具故障，也没有端点故障。没有调用 LLM。

## 预注册判定：`B_GAPS_RECORDED`

| 关系类型 | 状态 | 依据 |
|---|---|---|
| call_typed_attribute（Authlib `jwt.py:104`） | **EXPRESSIBLE_NOT_RECOVERED** | 校准结果为可表达，但 CodeQL 在两侧都找不到从 source 到 sink 的完整路径 |
| registry_dispatch（Authlib `jws.py:106-109`） | NOT_EXPRESSIBLE_BY_ANY | 校准结果为 false |
| guard_property（Caddy 2xx 匹配器） | NOT_EXPRESSIBLE_BY_ANY | 事先就登记为 false |
| object_composition（Caddy 的 Routes 和 HandleResponse） | NOT_EXPRESSIBLE_BY_ANY | 校准结果为 false |
| field_flow（File Browser 的 `nameInArchive` → `NameInArchive`） | NOT_EXPRESSIBLE_BY_ANY | 校准结果为 false |

- Trailmark：按事先登记，所有关系都是 NOT_EXPRESSIBLE。函数粒度的路径方面，Caddy 和 File Browser 找到了（source 和 sink 在同一个函数里，这本来就是显然的）；Authlib 没找到（调用被解析成了 proxy）。函数粒度的证据在行级评分中不计分。
- CodeQL：在所有 fixture 上都找到了 0 条路径。

**这只是冻结查询、默认设置下这个基线的操作性边界。** 它不能说明 CodeQL 这门语言、或者其他 provider，原理上无法表达这些关系（§9.3）。

## 预测与结果对照（`spike-p-predictions.md`）

| 项目 | 预测 | 结果 |
|---|---|---|
| call_typed_attribute 校准 | true | true ✓ |
| registry_dispatch 校准 | false | false ✓（但理由只说对了一半，见下文） |
| field_flow 校准 | true | **false ✗** |
| object_composition 校准 | true | **false ✗** |
| 决策 | `B_LIMITED_SCOPE_TO_1A`（或者 GAPS） | `B_GAPS_RECORDED` |

## 事后诊断（在冻结分数之后进行，不改变判定）

在 pilot 和评估的数据库上，另外单独跑了一个查询，查看 taint 实际传播到了哪里。冻结查询本身没有改动。

1. **Authlib：typed attribute 这一跳其实解析成功了，断点在派发。** 从 `s` 出发的 taint 经过 `jwt.py:104`，进入 `jws.py` 的 `deserialize_compact`（第 77 行），一直传到第 107 行 `algorithm.verify(signing_input, signature, key)` 的实参。但从注册表里取出来的 `algorithm`，其方法调用没有被解析，taint 没有到达 `jws_algs.py`。这和 pilot 里 registry 那组的断点一致。
   → **call_typed_attribute 被判为「未恢复」，是评分只认端到端完整路径造成的：下游的派发一断，整条路径就不存在了。** 这一跳本身是走通了的。
2. **Go 的 field_flow 和 object_composition：taint 不会从字段抬升到包含它的容器。** 在 pilot 里，taint 能走到结构体字面量里的字段、或者对某个字段的写入，但不会传到包含它的结构体或切片；而这里的 sink 是整个结构体。评估中 File Browser（`NameInArchive` → FileInfo → 切片 → `Archive`）和 Caddy（Routes → handler → HandleResponse → 返回值）走的都是同一种模式。
3. **Python 的 registry_dispatch：连派发本身都没有被解析。** 我当初预测的理由是「选择那一步不在路径上」，实际情况更严重：对从字典里取出来的实例调用方法，这个调用根本没有被解析；`TABLE[label]` 的结果也不会因为 key 带 taint 而被标记为 taint。

## 从中得到的认识

1. **在默认设置下，现有 provider 都提供不了 golden 所要求的可达性证据。** 缺口有三处：
   - **容器抬升**（Go 的字段 → 结构体 / 切片）：用 CodeQL 的通用设置（比如在 sink 处允许隐式读取）很可能就能解决。它不是某个 fixture 特有的问题，是最容易处理的一个。
   - **以数据为 key 的派发**（注册表 → 方法调用）：需要为派发建模，最难。
   - **guard property**：需要另写一个查询，列出路径所经过对象的兄弟字段。
2. **以端到端路径为单位来测量，会把各个关系混在一起。** 同一条链上只要有一个关系断了，前后已经解析成功的跳也会一并被判为未恢复。如果要让 provider 负责提供证据，证据应该是**逐跳的（hop 级）**，而不只是端到端路径。
3. 这个结论和 v1.1、v2 的结果放在一起，是互补的：agent 能用文字说明路径，但没有按 golden 要求的粒度引用出来；provider 在默认设置下，这些跳本身就断了。

## 下一步的选项（依据 §9.6，需要另行决定）

- **P-extension（扩展 provider）**：把以下能力作为通用设置，各自先在合成 pilot 上校准、预注册，然后再评估：容器抬升（隐式读取）、逐跳证据（部分流）、guard property 查询、注册表派发建模。其中容器抬升和逐跳证据最有可能做成。
- **混合方案（接近 v3）**：由 agent 提出逐跳的路径（v1.1 和 v2 已经表明它能用文字描述出来），再由 provider 用局部查询逐跳核验；核验不了的跳（比如注册表派发）明确标记为盲区。这最符合原来的分工：「agent 负责调查语义，provider 负责核验证据」。
- **缩小 B 的范围**：承认可达性证据只能部分自动化，产品层面给出「语义翻转点 + 未经核验的路径 + 盲区」。
