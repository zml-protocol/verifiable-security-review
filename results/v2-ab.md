# v2 报告：显式路径引用（同期 A/B）

- 协议：v2（冻结于 `54b964d`；额度失败的修复见 `faeff09`）。各组分数冻结于 `0b73082`，组间比较记录在 `4d48fe6`（`v2-compare.json`）。两次提交都在查看任何 v2 transcript 之前完成。
- 模型：`claude-sonnet-5`，effort `high`；Claude Code 2.1.280；订阅登录。
- 规模：80 个配对 block × 2 组 = 160 个 slot，最终全部 `VALID`。
  - block 1–22 第一次尝试就完成。
  - block 23–80 的第一次尝试撞上了订阅每周额度（被误判为 VALID 的问题已修复，改为 `INFRA_INVALID: usage_limit`）。额度恢复后，第二次尝试完成，每个 block 仍按 control/treatment 配对同时执行。

## 预注册判定：FAIL

| 条件（§8.4） | control | treatment | 门槛 | |
|---|---|---|---|---|
| 证据完整且归因正确率 | 13.8% | **21.2%** | treatment ≥ 60% | ✗ |
| 组间差 | | **+7.5 个百分点** | ≥ +20 个百分点 | ✗ |
| 归因正确率 | 97.5% | 97.5% | ≥ 80%，下降不超过 10 个百分点 | ✓ |
| 样本下限 | | 80/80 个配对，所有单元都是 5/5 | 每个单元 ≥ 4/5 | ✓ |
| harness 不变量（含上下文泄露） | 全部为 0 | 全部为 0 | 0 | ✓ |

按 §8.6 的约定：treatment < 60%，说明**光靠 prompt 不够**，按计划下一步是 v3（结构化的 `path_evidence` 字段）。golden 不做任何修改。

## 报告项（§8.5）

| fixture | control：证据完整 / 路径被引用 | treatment：证据完整 / 路径被引用 |
|---|---|---|
| Authlib | 5% / 23% | 30% / 57% |
| **Caddy** | **0% / 0%** | **0% / 0%** |
| File Browser | 25% / 35% | 28% / 46% |

翻转事实的引用率：control 94.7%，treatment 97.6%。

按 hypothesis 的证据完整率（control → treatment）：Authlib H1 10→30%，H2 0→30%；Caddy H1、H2 都是 0→0%；File Browser H1 50→70%，H2 0→10%，H3 40→20%，H4 10→10%。

## 事后分析（不改变判定）

1. **明确要求有效，但不够。** treatment 的路径引用率在 Authlib 从 22% 升到 57%，在 File Browser 从 35% 升到 46%。但证据完整率要求 base 和 head **两侧**都有完整的路径事实，而且每个事实都要同时引用多个位置，所以证据完整率只小幅上升。
2. **Caddy：agent 理解的「路径」和 golden 定义的不一样。** 两组都在 19/20 个 run 里引用了 2xx 匹配器和运行时的 `reverseproxy.go`（运行时实际执行 handle_response 路由的代码），但挂载 copy 路由的那两行（`goodResponseHandler.Routes = append(...)`、`rpHandler.HandleResponse = append(...)`），在 treatment 里也只被引用了 1–7 次。agent 把「配置结构 + 运行时执行」当作路径，golden 要求的是「配置的挂载关系」。按预注册，这不构成修改 golden 的理由，只记录为一个**测量效度上的问题**。
3. **File Browser：路径代码 100% 被读到过，但很少被引用。** 最常漏掉的是写入归档条目名那一行（`NameInArchive: nameInArchive`）。
4. **同一条件下重复实验的波动很大（历史参考，不参与 v2 统计）。** v1.1 只看 forward 和 swapped 时，证据完整率是 22.5%（归因 97.5%）；v2 的 control 组用的是同一个 prompt，得到 13.8%。两者差了 8.7 个百分点，说明没有同期对照的话，这项比较没法解释。v2 采用同期配对设计，这个判断是对的。

## 需要讨论的问题（下一步由用户和 Codex 决定）

- **按 §8.6 进入 v3**：新增结构化的 `path_evidence` 字段，golden 不变。但从机制 2 看，如果 agent 对 Caddy 的「路径」理解本来就不同，即使加了结构化字段，Caddy 也很可能仍然是 0%。
- **重新考虑问题的切分**：路径证据（可达性）本来就是 Spike 1A 的结构化 provider 应该提供的东西。如果让 runtime 或 provider 提供可达性，agent 只负责翻转点的语义判断，而翻转事实的引用率已经是 95–98%，那么 agent 引不引用路径就不再关键。这更符合最初的架构原则「provider 产出证据，agent 负责调查语义」。不过，Caddy 的路径是配置层面的挂载关系，调用图可能也捕捉不到，这一点需要另行验证。
