# Spike P：provider 的定向可达性

问题、规则和判定标准见 [PREREGISTRATION.md §9](../../PREREGISTRATION.md)。不调用 LLM。

```bash
# 1. §9 第一次冻结之后
uv run python experiments/provider_reach/reach.py fetch-codeql      # 下载固定版本的 bundle 并校验 sha256
uv run python fixtures/_pilot/build_goflow.py                       # pilot 用的合成模块
uv run python fixtures/_pilot/build_pyregistry.py
# 2. pilot（只跑非评估代码）：检查流程能否跑通，并校准 CodeQL 的表达能力
for p in trailmark codeql; do
  uv run python experiments/provider_reach/reach.py run --provider $p \
      --spec experiments/provider_reach/pilot.yaml --out runs/provider_reach_pilot
  uv run python experiments/provider_reach/reach.py pilot-check --provider $p
done
# 3. 把 results/spike-p-calibration.json 和第二次冻结一起提交；之后才碰评估 fixture
for p in trailmark codeql; do uv run python experiments/provider_reach/reach.py run --provider $p; done
uv run python experiments/provider_reach/reach.py score           # → results/spike-p-reach.json
```

| 文件 | 内容 |
|---|---|
| `endpoints.yaml` | 端点（provider 能拿到的唯一输入）、每个 golden 位置的关系类型、事先判定的表达能力 |
| `queries/{python,go}/ReachCommon.qll` | 端点匹配和 flow 设置（只使用默认 step），两个查询共用 |
| `queries/{python,go}/ReachTaint.ql` | 每种语言一个通用 taint 路径查询 |
| `queries/{python,go}/ResolveEndpoints.ql` | 确认端点确实解析到了节点（用来区分流程故障和能力结果） |
| `reach.py` | 下载、运行（Trailmark 或 CodeQL）、评分、pilot 检查 |
| `pilot.yaml` | pilot 的端点、预期经过的行，以及 plumbing / calibration / info 角色（不含评估 fixture） |
