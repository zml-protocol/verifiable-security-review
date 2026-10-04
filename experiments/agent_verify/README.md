# Spike 1B：跨 revision 的 agent 取证

问题：给定一个 hypothesis，agent 能不能在 base 和 head 上**分别**、**正确地**取证？指标和阈值见 [PREREGISTRATION.md §1B](../../PREREGISTRATION.md)。

## 运行

```bash
# 阶段 1：synthetic 热身（80 次）
uv run python experiments/agent_verify/run.py fixtures/synthetic-notes/case.yaml \
    --model claude-haiku-4-5-20251001 --max-budget-usd 1 --jobs 4

# 阶段 2（protocol v1.1）：先按固定顺序跑 gate 的 5 个 slot
CASES="fixtures/authlib-jws-none/case.yaml fixtures/caddy-forward-auth/case.yaml fixtures/filebrowser-archive-backslash/case.yaml"
uv run python experiments/agent_verify/run.py $CASES --model claude-sonnet-5 --effort high \
    --max-budget-usd 3 --total-budget-usd 200 --jobs 1 \
    $(grep -v '^#' experiments/agent_verify/stage2_gate.txt | sed 's/^/--slot /')
# 只根据计费推算预算并按规则裁剪，然后按它输出的 --conditions/--repeats 跑完其余 slot
uv run python experiments/agent_verify/budget.py plan $CASES \
    --label claude_claude-sonnet-5_high --gate experiments/agent_verify/stage2_gate.txt

uv run python experiments/agent_verify/score.py fixtures/<case>/case.yaml
```

- `--dry-run`：只生成 session 并打印命令，不调用 agent。
- 已经 finish 的 run 会被跳过，中断后重跑即可续上。重跑某一格时，删掉对应目录就行。
- 输出位于 `runs/agent_verify/<protocol>/<case>/<hyp>/<condition>/<agent>_<model>[_<effort>]/r<k>/`：

| 文件 | 内容 |
|---|---|
| `session.json` | 这次 run 用到的 commit、hypothesis 和屏蔽规则 |
| `transcript.jsonl` | 每一次工具调用，包括被拒绝的调用及其错误码 |
| `state.json` | observations、blind spots，以及所有签发过的 anchor（带 commit，供审计） |
| `agent.jsonl` / `agent.stderr` | agent CLI 的原始输出 |
| `meta.json` | 退出码、耗时、命令行 |
| `score.json` | 这一次 run 的评分 |

## 条件

| 条件 | base | head | 检验什么 |
|---|---|---|---|
| `forward` | 原 base | 原 head | 正常情况 |
| `swapped` | 原 head | 原 base | 结论应该镜像翻转（例如 CHANGE_IMPLICATED 变成 FIX_IMPLICATED） |
| `identity_base` / `identity_head` | 同一个 commit | 同一个 commit | base 和 head 的组件状态必须一致 |

## 隔离情况

- **Claude**：只挂载 secreview 的 MCP 工具。冒烟 run 的 init 事件确认了只有这 11 个工具。
- **Codex**：不在 protocol v1 范围内。`codex_cmd` 保留但从未跑过；它关不掉 shell，scorer 会在 `foreign_tools` 里把用过 shell 的 run 标出来。

## 工具

`get_task`、`list_files`、`read_code`、`search_code`、`find_symbol`、`changed_files`、`diff_file`、`map_location`、`submit_observation`、`submit_blind_spot`、`finish`。

Spike 1A 接入 Trailmark 之后，会再加一个 `get_structural_paths`。
