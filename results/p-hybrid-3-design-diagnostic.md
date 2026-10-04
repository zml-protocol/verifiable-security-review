# P-Hybrid-3 设计诊断（设计信息，不是结果；§12.0）

- 规则在第一次运行前提交（`41fbeaa`，见 `experiments/hop_chain/diagnose.py`）。
- 只读取 P-Hybrid-2 的 15 个共享初稿；两组的 final 有意不读。没有调用 LLM，也没有重评分：P-Hybrid-2 的判定不变。

## 初稿中已经构成完整链的 block 数（两个 revision 都完整）

| fixture | golden 严格匹配 | C1（节点身份） | C2（C1 + 同一对象） |
|---|---|---|---|
| Authlib | 5/5 | 5/5 | 5/5 |
| Caddy | 1/5 | 1/5 | **5/5** |
| File Browser | 3/5 | 3/5 | 3/5 |
| 合计 | 9/15 | 9/15 | **13/15** |

## 读法

1. **C1 与 golden 严格匹配完全相同。** 在端点规则 G 下，Caddy 和 File Browser 的「链」只有 1 条边，Authlib 只有 2 条，所以按节点身份的链匹配等于把 golden 覆盖换了个名字，没有任何放宽。在 C1 下，完整性反馈会奖励「选对 golden 节点」，而不是「给出成立的链」，这个构念是无效的。
2. **C2 把 Caddy 从 1/5 提高到 5/5。** 所有 Caddy run 的初稿里，都有由已核验的跳组成的链：`handler → Routes 写入`，guard 挂在 `Routes` 写入上，`goodResponseHandler`（定义）→ `HandleResponse`。只是同一个对象用了不同的节点来代表（定义 178 与写入 198）。C2 目前是基于源码文本的启发式，要用于正式协议，必须先变成冻结的、有测试的 resolver。
3. **剩下 2 个不完整的 block 都是 File Browser 的起点问题。** agent 从翻转行（`ToSlash` / `ReplaceAll` 对 `nameInArchive` 的重新赋值）出发，而不是从 golden 的起点定义（125）出发。r4 还用 `unsupported` 表达了从入口出发、跨函数的那一步。五类关系表达不了「定义 → 同一变量的下一个定义」，所以在 G 下这两个 block 不完整。这是端点规则的问题，不是 agent 没找到路径。
4. **对 A/B 设计的含义：天花板。** 在 C2 下，15 个初稿中有 13 个已经完整，一位的完整性反馈只在 2 对中可能携带信息，而且这 2 对都是上面的起点问题。按「以处理前的协变量停止」来算，要攒够 12 个不完整的初稿，大约需要 90 个 block，而它们几乎全部会是 File Browser 的起点问题。
5. **Spike P 的端点在五类关系下不可表达**（见 §12.0）。「产品级 entry」只能取 golden 链的起点。跨 Go 函数的调用是冻结核验器的盲区。
