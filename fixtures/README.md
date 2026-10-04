# Fixtures

> These are historical development fixtures used to build and test the evidence architecture, not
> the final fresh RD sample. See [`docs/RESULTS.md`](../docs/RESULTS.md) for the result hierarchy and
> [`experiments/rd/truth/fixtures/`](../experiments/rd/truth/fixtures/) for the fresh real-fix truth
> artifacts. The notes below preserve the fixture-development workflow.

每个 case 一个目录：

```text
fixtures/<case-id>/
  case.yaml     agent 能看到的内容：hypothesis，以及仓库、commit、屏蔽规则等 harness 配置
  golden.yaml   答案，绝不暴露给 agent
  build.py      （可选）合成仓库的生成脚本
```

模板见 [case.template.yaml](case.template.yaml) 和 [golden.template.yaml](golden.template.yaml)。

## 待办：语义 fixture（protocol v1，见 PREREGISTRATION.md §3）

| case | CVE | base → head | 状态 |
|---|---|---|---|
| `authlib-jws-none` | CVE-2026-28802 | `21f7f50820f3` → `a61c2acb8074` | 执行真值已完成；case/golden 草稿待独立审查 |
| `caddy-forward-auth` | CVE-2026-30851 | `00f948c6056f` → `05cfb121ec3f` | 同上（执行使用最小宿主，见 PREREGISTRATION.md §3.5） |
| `filebrowser-archive-backslash` | CVE-2026-62843 + CVE-2026-54093（修复） | `0231b7ebdfbe` → `847d08bdd135` | 同上（执行结果修正了原先的标签） |
| `gogs-option-injection` | CVE-2026-52806 | ? | 暂缓：引入 commit 未定位 |
| `openwebui-kb-idor` | CVE-2026-45398 | `2054ee0^` → `2054ee0` | 暂缓：「不要错误归因」困难案例，需先核实 base 上本来就有漏洞 |

裸克隆已放在 `.cache/repos/{authlib,caddy,filebrowser}.git`。

**golden 必须在该 fixture 的第一次 agent run 之前写完并提交。**

## 加一个真实 CVE case 的步骤

1. **定位修复 commit**：从 advisory 或 GHSA 找到修复 PR 或 commit。
2. **定位引入 commit，而不是修复 commit**：对修复 diff 删除或修改的行做 `git blame <fix>^ -- <file>`，一直往回追，找到让漏洞成立的那个改动（SZZ 的思路）。追不到单一引入点时，在 `notes` 里写清楚。
3. **判断归因类型**：
   - 引入 commit 删除或削弱了原有保护 → 期望 `CHANGE_IMPLICATED`（forward）
   - 漏洞随功能一起诞生 → base 上目标不存在，属于 INTRODUCED 路径。现阶段 derive 还不处理 `TARGET_ABSENT`，要在 golden 里标明，并考虑换一个 case
4. **固定 commit**：`base` 设为引入 commit 的父 commit，`head` 设为引入 commit，都用完整 SHA。
5. **克隆到本地**：`git clone --bare <url> .cache/repos/<case-id>.git`，然后把 `repo.path` 指向它。必须完整克隆，不能用 partial clone，否则 agent 运行时会联网拉取对象。
6. **补充屏蔽规则**：如果仓库里有会直接点名漏洞的文件（docs/advisories、release notes 等），写进 `deny_paths`。
7. **写 hypothesis**：真假大约 1:1，其中一个负对照放在改动附近。
8. **写 golden**，然后跑 `uv run pytest tests/test_derive.py`，检查 golden 是否自洽。

## hint 的规矩

hint 模拟的是候选生成器（Spike 1A）的输出，所以只能给出**入口**和 **sink**。指向「决定答案的控制点」的 hint 等于泄露了答案。hint 不区分 revision，swapped 条件下不需要改写。

## 负对照怎么写

- 容易的负对照：claim 和代码明显矛盾（例如 synthetic-notes 的 H2：路由上有 `@require_login`）。
- 难的负对照：落在这次改动碰过的地方，但结论没变（例如 H4：owner 检查从 handler 挪进了 service，并没有消失）。**每个 fixture 至少要有一个这种。**
