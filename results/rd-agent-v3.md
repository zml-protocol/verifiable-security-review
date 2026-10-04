# RD agent v3 终止报告

## 结论

RD v3 在任何模型测量之前以 `CALIBRATION_INVALID` 终止。一次性 held-out batch 已由独立
curator 生成并提交，但冻结 validator 拒绝其中一个 Go behavior anchor。按照预注册的终止规则，
该 batch 不得修补、替换、重排或重新生成；因此没有启动 20 个 Claude A-only 会话、provider
held-out challenge、fresh fixture 选择或 formal tranche，项目关闭且不开 v4。

这不是 Claude treatment 的失败结果，也不能产生 A、B、C1 或 C2 的能力估计。项目最后一份有效
模型测量仍是 RD v2：它是 `harness_ok=true` 的 valid fail，并显示当前 agent/provider treatment
未达到 verified-reasoning 标准。

## 终止点

| 项目 | 结果 |
|---|---|
| 冻结 treatment | `treatment-freeze-v2.json`，SHA-256 `36935e6e…3828` |
| 冻结构造协议 | `construction-freeze-v2.json`，SHA-256 `74a4a76c…bf0` |
| curator | `codex-independent-no-context`，independence attestation = true |
| sealed batch | 20 个 A cases、3 个 provider cases |
| aggregate SHA-256 | `10b696811d8529459d428fa702fb23e2a4efcb4e04e7cfb263628f783a4cd97f` |
| batch commit | `d2f655e` |
| validator 结果 | `CALIBRATION_INVALID`，commit `906442d` |
| Claude/provider/formal 调用 | 0 / 0 / 0 |
| API-equivalent 支出 / overshoot | `$0 / $0` |

冻结 validator 在 `go-claim-specific-entry-02` 的 `behavior.revision_A` 停止：

```text
coralpager.go:9  queue <- canonicalTopic
resolved node:  *ast.SendStmt
```

该行在 Go 语法上是完整的 send statement；但冻结的 A construction validator 只接受
`*ast.AssignStmt`、`*ast.ReturnStmt` 和 `*ast.IfStmt`。因此它不满足实际执行的 held-out
acceptance contract。

## 根因解释

这是 public curator contract 与 frozen validator 之间的接口不完备，而不是 held-out 模型表现：

- curator 获得的公开规则要求“exact complete statement”；
- 公开 A schema 定义 anchor 的文件、行号与表达式字段，但没有枚举允许的 AST node types；
- 独立 curator 按自然语言把 Go send statement 当作完整语句；
- 只有未向 curator 开放的 construction validator 实现包含更窄的三类 whitelist。

换言之，batch 对公开规则是合理的，但对真正的冻结 validator 不可采。预注册的 one-shot 规则不允许
在解封后把这解释成一个可修复的小格式问题；否则就会形成“看到 held-out 后补 contract”的适应路径。

## 可以与不可以得出的结论

可以得出：

1. fail-closed gate 有效工作，在首个计费调用前阻止了不可比较的测量；
2. 独立 challenge authoring 需要把 validator 的完整可接受语言作为公开、可执行 contract，而不能只给
   自然语言中的“complete statement”；
3. RD v2 揭示的核心差异仍成立：正确安全归因并不等于提交了满足冻结证据标准的 reasoning artifact。

不可以得出：

- v3 A calibration 是否能达到 16/20；
- provider extension 是否安全或覆盖更广；
- v3 treatment 是否优于 v2；
- fresh real fixtures 上的 B、C1 或 C2 表现。

## 项目终态

RD v3 的冻结协议明确规定：synthetic gate 任一条件失败即发布具体终态、不得进入 fresh fixtures，并关闭
项目；同时不存在 v4 路径。这里执行该规则，不用重抽 batch 或改 whitelist 来“救”最后一轮。

项目最终证据由两部分组成：RD v2 提供有效但失败的 agent 能力测量；RD v3 提供一次有效的预测量协议
拒绝，暴露 independent-curator/validator contract 的隐藏不一致。二者共同支持保留分层验证框架与严格
质量门，但不支持宣称当前 workflow 已达到 verified reasoning。
