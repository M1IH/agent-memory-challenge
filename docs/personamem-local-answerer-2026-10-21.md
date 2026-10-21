# PersonaMem-v1 32K 本地答案级基线（2026-10-21）

## 初始离线条件

- 只用公开 development 414 题；175 个 frozen_holdout 未使用。标准化数据 SHA-256 `0f4a1d1536f196d5986b240bb6cddbcb55ee72d0f1055abec7694731189bd0f0`。排除上游含合成 persona 的 system turn，按每题原始截止位置重放 user/assistant 消息。
- 本机 Ollama 模型 `qwen3-vl:4b-instruct`，digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`；温度 0、seed 0、`num_predict=24`、`num_ctx=8192`。固定 system prompt SHA-256 `dc3a1c8f0225ac48277461f0237c77bb514ad41dae5e3164560bca200de841ec`。
- 无记忆：只给最新消息与四个选项。初始检索条件：第四版 `app/` 词法 Add/Search，查询为最新消息，**`options=None`**，Top-5 片段作为证据给同一模型。每题独立 user ID，避免交叉污染。运行器 SHA-256 `ad651f9042273b36cf56def511ee2d9f7772654af1d023057014e61251c413c8`。
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

最重要的下一步是检查 21 个回退和 `track_full_preference_evolution`：当前“只用最新消息检索 Top-5”可能缺少偏好变化的多个阶段。初始对照没有把选项传给 Search，不能代表生产多选请求的完整路径。

这是本机 Qwen 4B 对公开数据的答案级诊断。官方 AML 使用的平台侧回答模型、提示词、隐藏题分布与这里不同，因此 **54.11% 不是 Smoke 或 Full 分数**，也不足以授权下一次官方评测。

## 发展集候选冻结

只改检索证据选择，不改模型与答案提示词：先按最新消息 Search Top-5，保留前 3 条；再按“最新消息 + 四个选项”Search Top-5，按顺序补足 5 条，去掉重复 memory ID。这一 `balanced_union` 候选在同一 414 题严格计分为 240/414，基线为 224/414；34 题改善、18 题回退。按开头标签解析为 245/414 对 231/414。发展集逐题报告 SHA-256 `ce8bb7de15281bb7287fcfe9ec27666303292152200246f6dc358ce4b376cea6`，配对比较 SHA-256 `55a5766f2764bdfc7deab71b8282ce10df800702e8db8598498e494f05c3eb44`。

直接把全部选项拼进单一查询虽然达到 232/414，却使 `recall_user_shared_facts` 从 46/95 降到 38/95，因此淘汰。`balanced_union` 总分更高，但该类仍从 46/95 降到 44/95；这项回退必须在冻结留出和后续错误分析中单独审查，不能只看总正确数。

2026-10-21 已按上述计划运行冻结留出，但随后发现原版 Search 在 `options` 非空时已有独立的 0.35 倍选项证据评分，而初始基线一直传入 `options=None`。因此这次冻结留出 **已经打开**，且 81/175 → 92/175 仅说明 question-only 离线条件下的提升，不能作为生产同构验收。见下节口径审计。

## 生产同构口径审计与候选结论

以 `store.search(query=最新消息, options=四个选项, top_k=5)` 作为第四版原版多选路径，保持同一 Qwen 模型、提示词、参数、题目和 Add 重放。`balanced_union` 仍用问题结果前三条加“问题+选项”结果补足五条。两者按题目 ID 配对：

| 集合 | 原版 `native_options` | `balanced_union` | 改善 / 回退 | 结论 |
| --- | ---: | ---: | ---: | --- |
| development 414 | 224 | 240 | 35 / 19 | 有探索性增益 |
| 已打开的 holdout 175 | **97** | **92** | 7 / 12 | 候选失败，不能部署 |

留出集严格格式差额为 -5 题；只解析开头标签时为 98 → 95，方向不变。留出中 `recall_user_shared_facts` 为 18/34 → 16/34，`suggest_new_ideas` 为 7/23 → 6/23，`track_full_preference_evolution` 为 23/48 → 22/48。初始 question-only 基线在同一留出为 81/175，说明遗漏 `options` 会显著低估原版表现。此留出集不再作为未来候选的全新盲测使用，也不据其逐题结果调整 `balanced_union`。

生产同构原版的本地报告 SHA-256：development `c1be92e7f6f303a5ead35bc3a788efb47e185cb817ebafb7da77607114335c85`，已打开的 holdout `28a849e826b3e7391d058bb27892d74b21ff8a9743f2a5fa7f412cc94e427a6b`。配对比较报告分别为 `65a9415d3f0634471b41026ed1717d6ca1a65a73b7709460c5d895757abbb4f1` 与 `b44b50134d318c18db0578c7d228f79530cb5b58626e15735e055a2de90ca9bb`，均留在忽略版本控制的 `data/`。

结论：**淘汰 `balanced_union`；保持线上第四版不变。**后续在另一个独立来源或新冻结数据上验证新的能力级候选。现有所有数值仍是本机 Qwen 4B 的公开数据结果，不是官方分数。

官方 [API Guide](https://agentmemoryleaderboard.ai/api-guide) 已在 2026-10-21 核对：选择题 Search 确实传入顶层 `options`，正式评测 `top_k=100`，统一 Answer 最多接收约 117,760 个输入 tokens。这进一步确认 `native_options` 才是多选检索的协议基线。本报告的 Top-5 与 Qwen 8,192 上下文仅用于快速诊断，不能证明正式 Top-100 的答案增益或回退。
