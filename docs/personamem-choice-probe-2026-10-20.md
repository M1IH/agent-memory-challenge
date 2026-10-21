# PersonaMem-v1 32K 词法选项诊断（2026-10-20）

这是一条公开数据上的无生成模型诊断线，不是官方 Smoke、PersonaMem 标准答案模型，也不能预测正式分数。

## 输入与方法

- 使用官方 PersonaMem-v1 32K revision `a8076d5608c93ba2a28983cd78aa99b01a163ae7`，标准化文件 SHA-256 `0f4a1d1536f196d5986b240bb6cddbcb55ee72d0f1055abec7694731189bd0f0`。只运行 414 个 development 样本，175 个 frozen_holdout 未使用。
- 适配器按每题 `end_index_in_shared_context` 截断，排除含合成 persona 的 system 消息；按 session 重放 user/assistant 消息。每题使用独立 user ID，关闭 embedding，运行第四版 `app/` 词法检索。
- 对每个选项文字分别 Search Top-3，取最高检索分数，除以不同查询词数量的平方根，选择最高分；平分时取靠前选项。这是固定的启发式，不能替代平台侧 `gpt-4o-mini` 答题。
- 命令：`py -3.13 -m benchmarks.run_personamem_choice_probe --limit 414 --output data\personamem-dev-lexical-choice-414.json`。运行器 SHA-256 `c3237b095e265b20c91556088a8bbfc9a6cd7cb902c6a8ad69b4d7702f0241a2`；逐题报告 SHA-256 `bbdf492839c606f3023356b2895edd1375ec1e374d642697ded077744a46c135`，只保留在忽略版本控制的 `data/`。

## 结果

| 能力 | 正确/总数 | 准确率 |
| --- | ---: | ---: |
| 全部 | 175/414 | 42.27% |
| recalling_the_reasons_behind_previous_updates | 48/64 | 75.00% |
| recalling_facts_mentioned_by_the_user | 10/14 | 71.43% |
| provide_preference_aligned_recommendations | 23/43 | 53.49% |
| track_full_preference_evolution | 37/91 | 40.66% |
| suggest_new_ideas | 27/70 | 38.57% |
| generalizing_to_new_scenarios | 12/37 | 32.43% |
| recall_user_shared_facts | 18/95 | 18.95% |

相同 414 题固定选择第一个选项为 98/414（23.67%），仅作无记忆的粗略参照。两个方法没有相同的回答模型，差异不能解释为检索系统的正式增益。最明显的诊断缺口是 `recall_user_shared_facts`，其次是新场景泛化和偏好演化；先在发展集分析选项分数、来源文本与冗余，再设计一个候选并用固定回答器验证，不能按当前启发式结果直接修改线上排序。

2026-10-21 追查：在 `recall_user_shared_facts` 的 77 个错误中，抽查发现选项探针会把“喜欢做音乐”与“讨厌音乐制作”按共词错误匹配。仅改变选项长度归一化指数，95 题中的正确数仍在 17–23 之间；因此 18/95 主要证明这个无生成模型启发式不足，不能推断生产记忆缺失。使用固定本地回答模型后，同类 95 题从无记忆 12 题提升到检索后 46 题，见 [答案级基线](personamem-local-answerer-2026-10-21.md)。
