# Spike 1A：结构候选的信噪比（待做）

问题：Trailmark 的 graph-evolution 在普通 PR 上，能不能产出**少而有用**的 hypothesis 种子？指标和阈值见 [PREREGISTRATION.md §1A](../../PREREGISTRATION.md)。

## 计划

1. 安装 Trailmark，并锁定版本（v0.4 到 v0.5 之间 node/edge kind 改过）。版本号写进每次输出。
2. **先看原始输出，再写 adapter。** 在 synthetic-notes 和 1 个真实 PR 上直接跑 graph-evolution，确认它实际能表达什么（新入口、新可达路径、proxy/uncertain 边）。
3. `spike_trailmark.py --repo --base --head`：
   - 物化两个 revision：对每个 commit 做 `git archive` 到 `.cache/trees/<sha>/`，用 commit SHA 做缓存键；
   - 调用 graph-evolution；
   - 做最简单的归一化，得到候选列表（入口、sink、路径、置信度、unresolved 数）。
4. 抽样（按预注册分层）并逐个标注候选。
5. 在反转的修复 commit 上测 recall。

## 注意

- 物化目录只给 Trailmark 用；agent 仍然只通过 MCP 读取对象库。
- 盲区（proxy/uncertain 边）要和候选数一起统计，不能只看候选数。
