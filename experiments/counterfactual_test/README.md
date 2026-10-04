# Spike 1C：差分测试（待做）

问题：agent 能不能写出一个「在 head 上因断言而失败、在 base 上通过」的测试？这是 REFUTED（以及 REGRESSION 这一级）唯一现实的来源。指标见 [PREREGISTRATION.md §1C](../../PREREGISTRATION.md)。

## 计划

1. 在 Open WebUI（FastAPI TestClient）和 Gogs（Go test）中选 1 个。File Browser 需要 Windows 环境，先跳过。
2. 为 base 和 head 各准备一个可以跑测试的环境（容器），依赖在构建镜像时装好，**运行测试时断网**。
3. agent 的工具在 1B 的基础上，增加 `write_test(path, content)` 和 `run_test(revision)`。测试文件由 runtime 分别放进 base 和 head 的工作树。
4. 判定：看测试框架输出里的失败类型，只有断言失败算数。编译错误、导入错误、fixture 错误都算「未成功」。
5. 负对照 hypothesis 也要跑，「成功」次数必须是 0。

## 安全

- 测试代码由 LLM 编写，只能在断网、无宿主挂载的容器里运行。
- 只针对本地 fixture，不对任何在线实例发请求。
