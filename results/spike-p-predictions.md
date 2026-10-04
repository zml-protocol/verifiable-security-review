# Spike P：事先预测（与第一次冻结一起提交，在 CodeQL 下载之前）

这些预测**不影响任何分类，也不影响查询**（PREREGISTRATION.md §9.5）。不论校准和评估的结果如何，都直接采用冻结查询给出的结果。本文件只用于事后对照，看我们的事先判断有多准。

## 校准 pilot（CodeQL 冻结的 taint 路径查询）

| 关系 | 预测 | 理由 |
|---|---|---|
| call_typed_attribute | true | CodeQL Python 的类型追踪应该能从 `__init__` 中的属性赋值，一路解析到对该属性的方法调用 |
| registry_dispatch | **false** | taint 沿着输入里的 `proof` 流向 sink，而用键选择的那一步（`TABLE[label]`）作用在接收者一侧，不会出现在这条路径上 |
| field_flow | true | 标准库带有经过局部变量和结构体字段的 taint 步骤 |
| object_composition | true | 标准库带有 append 和字段写入的 taint 步骤 |

## 评估（参考用）

- Trailmark：按事先判定的表达能力，所有关系都是 NOT_EXPRESSIBLE。函数级路径方面，预计 Authlib（`decode` → `verify`）找不到，因为会被解析成 proxy。
- CodeQL：预计 Authlib 的 registry_dispatch 恢复不了（理由同上）；Caddy 的 object_composition 和 File Browser 的 field_flow 大概率能恢复；guard_property 事先判定为表达不了。
- 因此预计的决策结果是 `B_LIMITED_SCOPE_TO_1A`；如果 registry_dispatch 校准为 true 却没恢复出来，则是 `B_GAPS_RECORDED`。
