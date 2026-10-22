# LongMemEval 用户原话加权离线候选（2026-10-22）

候选：保持第四版 `MemoryStore.search` 不变，取原始 Top-100 后，按 `原分数 + b × 是否为 user 消息` 重排，`b` 分别为 0、0.5、1、2、4，平分按原始位置保序。仅使用消息角色与原分数，不使用参考答案参与排序。本试验是离线后处理，不是已部署服务。

固定公开 LongMemEval `s_cleaned` development 390 题、词法检索、Top-5 必要会话来源覆盖：

| 用户消息加分 | 必要会话完整覆盖 | 时序题完整覆盖 | 相对原版改善 / 回退 |
| ---: | ---: | ---: | ---: |
| 0 | 228/390 | 47 | — |
| 0.5 | 228/390 | 47 | 1 / 1 |
| 1 | 229/390 | 47 | 2 / 1 |
| 2 | 232/390 | 49 | 6 / 2 |
| 4 | 234/390 | 49 | 8 / 2 |

`b=2` 使 MoMA/Met 时序题的两个必要会话进入 Top-5，但连续慈善活动题仍缺关键用户事实。回退分别涉及单会话偏好和跨会话题；`b=4` 的回退涉及单会话偏好和知识更新。逐题 ID 和聚合结果保留于忽略版本控制的 `data/longmemeval-roleboost-probe.json`。

进一步用固定本地 Qwen 4B 回答器在同一 30 道公开 development 题上比较 `b=2` 与原版。运行命令：

```text
py -3.13 -m benchmarks.run_longmemeval_local_answerer --output data/longmemeval-s-dev-local-answerer-user-role-30.json --retrieval-mode user_role_boost --skip-without
```

原版严格 Exact Match 为 5/30；候选 4/30，0 题改善、1 题回退。唯一回退是 `e47becba`：原答 `Business Administration`，候选答 `You graduated with a degree in Business Administration.`，属于严格格式不匹配，不能据此断言事实能力下降。但也没有答案级增益，且来源代理存在回退，因此**淘汰全局角色加权**，不改线上 Add/Search。

局限：Top-5 会话来源覆盖不等于关键事实片段覆盖，更不等于官方答案正确率；本地模型、Top-5 和官方 Top-100 回答模型不同。下一候选应以具体用户事实片段进入返回前缀为辅助验收，并在独立公开答案任务和跨能力回归上证明净收益。
