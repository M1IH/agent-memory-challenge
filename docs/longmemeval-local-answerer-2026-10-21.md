# LongMemEval-S 本地答案诊断（2026-10-21）

## 固定条件

只取标准化 LongMemEval-S cleaned 的 development，按来源顺序每类前 5 题，共 30 题；不触碰 110 道 frozen_holdout。标准化文件 SHA-256 `ebe9672a76d0b1b0c28c1cf8020e94b939d1d47d8610a792b7e415024fbe4141`。每题隔离用户，逐会话重放原始 turn，按第四版生产词法 Search `options=None` 取 Top-5 片段。

本地回答器为 Ollama `qwen3-vl:4b-instruct`，digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`，温度 0、seed 0、`num_ctx=8192`、最多生成 80 tokens。提示词 SHA-256 `b1ef04417797a98a4dfd534b7062b6dbe15f27a2af2f1ef416d9fdfa6a7adb31`。无记忆条件只给问题；检索条件另给 Top-5 结果。使用本地严格大小写不敏感、空白归一的 exact match；它不是 LongMemEval 官方 judge。

命令：`py -3.13 -m benchmarks.run_longmemeval_local_answerer --per-capability 5 --top-k 5 --output data\longmemeval-s-dev-local-answerer-30.json`。运行器 SHA-256 `13af47cd26a48ab6a2c53ea27695829c9d65e2e73f40abef83b5b87838ef571f`；逐题报告在被 Git 忽略的 `data/`，SHA-256 `2cab4e64a44d02bcff2b91d46e156024b76d3f8e47907ad410f2d6ab5b7a2a21`。

## 观察

| 题型 | 题数 | 检索后严格 EM | 必要会话来源均在 Top-5 |
| --- | ---: | ---: | ---: |
| knowledge-update | 5 | 1 | 5 |
| multi-session | 5 | 0 | 0 |
| single-session-assistant | 5 | 2 | 5 |
| single-session-preference | 5 | 0 | 2 |
| single-session-user | 5 | 2 | 4 |
| temporal-reasoning | 5 | 0 | 3 |
| **合计** | **30** | **5** | **19** |

无记忆严格 EM 为 0/30。必要来源完整进入 Top-5 的 19 题中，仍有 14 题未达到严格 EM；12 题检索后回答以“不知道”开头。只去掉标点再比较时，正确数为 6/30。其他回答存在语义相近但表述不同、部分列举、具体数字错误等混合情况，不能把 25 个严格失败都归为检索失败，也不能把会话来源命中当作片段已提供答案。

这是极小、按来源顺序截取的本地诊断；Qwen 4B 的提示词和 8,192 上下文也不同于官方 Answer 条件。下一步区分 **必要句子未进返回片段**、**证据已进但回答失败**、**评分格式不一致** 三类，再在固定开发集上做单一候选对照。该结果不是 AML Smoke/Full，也不支持第五次正式评测。
