# P-Hybrid-1 报告：provider 逐跳核验（§10）

- 冻结 `ea2e4fd` → cal 运行一次，分数提交 `1397c64` → eval 运行一次，分数提交 `a4ce53d` → 路由判定 `827cf43`。
- 冻结前按 Codex 审查修改了路由：只有 cal 正常完成的关系才有资格进入 Hybrid-2。
- 所有运行都正常完成，没有工具故障。没有调用 LLM。CodeQL 2.27.1。

## 预注册判定：`HYBRID_2_LIMITED_SCOPE`

五种关系在 cal 和 eval 上都是 **SUPPORTED**，没有 UNSAFE，也没有 INCONCLUSIVE。可以进入 Hybrid-2 的关系为全部五种：`call_typed_attribute`、`registry_dispatch`、`field_flow`、`object_composition`、`guard_property`。在这五种关系之内，没有剩余的盲区。

| 关系 | cal：真跳 VERIFIED | cal：假跳 VERIFIED | eval：真跳 VERIFIED | eval：假跳 VERIFIED | eval：引用检查拦下 |
|---|---|---|---|---|---|
| call_typed_attribute | 3/3 | 0/3 | 2/2 | 0/8 | 0 |
| registry_dispatch | 6/6 | 0/5 | 2/2 | 0/8 | 0 |
| field_flow | 5/5 | 0/4 | 2/2 | 0/10 | 2 |
| object_composition | 4/4 | 0/4 | 2/2 | 0/10 | 2 |
| guard_property | 2/2 | 0/4 | 2/2 | 0/10 | 2 |

没有真跳被判为 CONTRADICTED。eval 中各变异类型的状态分布：

| 变异类型 | 状态 |
|---|---|
| reversed | 8 个 CONTRADICTED（形状检查），2 个 UNVERIFIED（object_composition 的 reversed，两端的种类都合法） |
| shift | 20 个 UNVERIFIED |
| wrong_target | 16 个 UNVERIFIED |
| wrong_revision | 6 个都被引用检查拦下，没有送入核验器 |

## 预测与结果对照（`p-hybrid-1-predictions.md`）

五种关系在 cal 和 eval 上的预测全部命中（都是 SUPPORTED），路由的预测（`HYBRID_2_LIMITED_SCOPE`，85%）也命中。registry_dispatch 在 eval 上事先只给了 50%，实际两侧都被核验到了：`cls.register_algorithm(algorithm)` 的接收者是一个持有类对象的参数，标准调用图解析成功了；跨模块导入的 `JWS_ALGORITHMS` 列表也没有造成断点。

## 事后诊断（在分数提交之后进行，不改变判定）

1. **注册表模型是 registry_dispatch 被核验到的全部原因。** 在 Authlib 的数据库上，去掉该模型（只用标准 step），`jws.py:107` 的调用一个目标都解析不出来，两侧都是 0 行。那样这个关系在 eval 上就是 BLIND，和 Spike P 的断点一致。
2. **它解析出的目标集合是精确的。** 带上模型后，`jws.py:107` 解析到的目标，恰好是已注册的六个 JWS 算法的 `verify`（None、HMAC、RSA、EC、RSA-PSS、EdDSA），也就是冻结前被跳过的那些真候选。没有解析到基类 `JWSAlgorithm.verify`；JWE 的同名类属性注册表 `JsonWebEncryption.ALGORITHMS_REGISTRY` 也没有被合并进来。
3. **call_typed_attribute 的三个调用都解析对了**：`jwt.py:78` → JWS 的 `serialize_compact`，104 → JWS 的 `deserialize_compact`，106 → JWE 的 `deserialize_compact`。所以两个 shift 变异和 wrong_target 变异得到 UNVERIFIED，是因为解析结果正确，而不是解析失败。

## 结论的边界

- **每种关系在 eval 上只有 2 个真跳**，而且 base 和 head 的两个真跳高度相关。「2/2」只能读作「在这些 golden 位置上可行」，不能当作覆盖率的估计。
- **eval 的 46 个送入核验器的负例，是从冻结的真跳系统变异出来的相关挑战用例**，不是从真实假跳总体中随机抽样的。「0 个被判为 VERIFIED」只说明**在这套预注册的变异挑战上，没有观察到误核验**，不能用来估计总体误报率。
- **核验器、golden 和 cal 都出自同一作者之手**，cal 只是执行留出。registry 模型是在 dev 上看到第一版 BLIND 之后加入的（§10.3 已披露）。
- **Hybrid-2 的「有限范围」指这五种关系类型、这种单跳形式。** 冻结的关系表以外的连接，例如 Caddy 在运行时由 `reverseproxy.go` 执行 handle_response，以及配置先序列化成 JSON、再按名字从模块注册表加载，仍然在范围之外（§9.7）。
- **本阶段没有回答 agent 会不会按这种格式提出跳。** v2 显示，agent 对 Caddy「路径」的理解和 golden 不同：它引用的是运行时执行，而不是挂载那几行。这正是 P-Hybrid-2 要测的问题。

## 对下一步的含义

混合路线中 provider 这一侧已经具备了条件：对这五种关系，冻结的通用核验器能够安全地判断单跳。问题转到 agent 一侧，下一步由用户和 Codex 决定。可以考虑的 P-Hybrid-2 方向是：agent 按 §10.1 的格式提交带类型的跳，由 runtime 调用冻结的核验器逐跳判定，再把 VERIFIED、UNVERIFIED、CONTRADICTED 反馈给 agent。可以测量：

- agent 提出的跳覆盖了多少 golden 链；
- agent 提出的跳里有多少被判为 VERIFIED；
- 有多少假跳（真值由人工事后标注）被误核验；
- 在 v2 中路径引用率为 0% 的 Caddy 上，这种结构能否改变结果。
