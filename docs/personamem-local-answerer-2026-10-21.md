# PersonaMem-v1 32K 本地答案级基线（2026-10-21）

## 固定条件

- 只用公开 development 414 题；175 个 frozen_holdout 未使用。标准化数据 SHA-256 `0f4a1d1536f196d5986b240bb6cddbcb55ee72d0f1055abec7694731189bd0f0`。排除上游含合成 persona 的 system turn，按每题原始截止位置重放 user/assistant 消息。
- 本机 Ollama 模型 `qwen3-vl:4b-instruct`，digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`；温度 0、seed 0、`num_predict=24`、`num_ctx=8192`。固定 system prompt SHA-256 `dc3a1c8f0225ac48277461f0237c77bb514ad41dae5e3164560bca200de841ec`。
- 无记忆：只给最新消息与四个选项。检索条件：第四版 `app/` 词法 Add/Search，查询为最新消息，Top-5 片段作为证据给同一模型。每题独立 user ID，避免交叉污染。运行器 SHA-256 `ad651f9042273b36cf56def511ee2d9f7772654af1d023057014e61251c413c8`。
- 命令：`py -3.13 -m benchmarks.run_personamem_local_answerer --limit 414 --top-k 5 --output data\personamem-dev-local-answerer-414.json`。逐题原始模型输出保存在忽略版本控制的 `data/`，报告 SHA-256 `185eae2e412f2f0597ea6f905deb3b5dda5779968c6613179eddf2a6ce0697bc`。

## 结果

| 能力 | 题数 | 无记忆正确 | 检索后正确 |
| --- | ---: | ---: | ---: |
| 全部 | 414 | 161（38.89%） | 224（54.11%） |
| generalizing_to_new_scenarios | 37 | 3 | 18 |
| provide_preference_aligned_recommendations | 43 | 22 | 30 |
| recall_user_shared_facts | 95 | 12 | 46 |
| recalling_facts_mentioned_by_the_user | 14 | 4 | 8 |
| recalling_the_reasons_behind_previous_updates | 64 | 46 | 47 |
| suggest_new_ideas | 70 | 14 | 20 |
| track_full_preference_evolution | 91 | 60 | 55 |

严格格式计分中，84 题从错变对，21 题从对变错，140 题两边都对，169 题两边都错。模型有时输出选项标签加一小段选项文字；只提取开头无歧义标签时，无记忆 165/414、检索后 231/414，结论方向不变。严格与解析计分均保留，避免把格式问题误写成记忆问题。

最重要的下一步是检查 21 个回退和 `track_full_preference_evolution`：当前“只用最新消息检索 Top-5”可能缺少偏好变化的多个阶段。先在 development 做可解释的证据覆盖候选，再用相同模型、提示词和题目重跑；冻结留出只在候选锁定后使用。

这是本机 Qwen 4B 对公开数据的答案级诊断。官方 AML 使用的平台侧回答模型、提示词、隐藏题分布与这里不同，因此 **54.11% 不是 Smoke 或 Full 分数**，也不足以授权下一次官方评测。

## 发展集候选冻结

只改检索证据选择，不改模型与答案提示词：先按最新消息 Search Top-5，保留前 3 条；再按“最新消息 + 四个选项”Search Top-5，按顺序补足 5 条，去掉重复 memory ID。这一 `balanced_union` 候选在同一 414 题严格计分为 240/414，基线为 224/414；34 题改善、18 题回退。按开头标签解析为 245/414 对 231/414。发展集逐题报告 SHA-256 `ce8bb7de15281bb7287fcfe9ec27666303292152200246f6dc358ce4b376cea6`，配对比较 SHA-256 `55a5766f2764bdfc7deab71b8282ce10df800702e8db8598498e494f05c3eb44`。

直接把全部选项拼进单一查询虽然达到 232/414，却使 `recall_user_shared_facts` 从 46/95 降到 38/95，因此淘汰。`balanced_union` 总分更高，但该类仍从 46/95 降到 44/95；这项回退必须在冻结留出和后续错误分析中单独审查，不能只看总正确数。

冻结留出使用同一数据、Qwen digest、提示词 SHA、温度、seed、Top-5 和 `balanced_union` 3+2 规则，不据留出结果调整参数。两条条件均只运行一次，按题目 ID 配对；若冻结留出总正确数不升或核心能力明显回退，候选不进入部署路径。
