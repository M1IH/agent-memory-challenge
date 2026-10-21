# CLBench 数据库规则记忆代理（2026-10-21）

## 来源与边界

一手仓库 `pgasawa/continual-learning-bench@5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26`，Apache-2.0，隔离检出在被 Git 忽略的 `data/clbench-source/`。该项目的 `database_exploration` 是跨 episode 的 SQLite 探索任务，原生指标同时取决于答案是否正确及探索查询次数；[任务说明](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/database_exploration/README.md)明确不能把它化约为静态问答。仓库原始问题文件含 SQL 与参考答案，本实验只把公开的**问题文本**送入 Search、用 `knowledge_dependencies` 作检索标签；SQL、答案、备注均未送入 Add/Search。问题与逐题报告只留在忽略版本控制的 `data/`。

手工把任务 README 描述的 12 类可复用知识写成独立记忆卡，包括产品组身份、表结构、价格与时间格式、外键、数据质量和迁移规则。每卡一个会话，统一用户写入第四版词法 `MemoryStore`；Search Top-5。`questions.json` 30 题、`questions_post_drift.json` 20 题全部用于**公开开发诊断**，并不等于原生 default schedule 的 20+20 题顺序。两文件 SHA-256 分别为 `452f1af2a4a24288b4d8ec4bda225c8e54ded359b82c119b6120b5ae0678c509`、`51109ae4f8be803b70cacd710d319e02b88d86a891ccd799f48cec8552bf711c`。

## 检索对照

| 查询条件 | 原始 30 题平均依赖 Recall@5 / 完整 | 迁移后 20 题平均依赖 Recall@5 / 完整 | 全部完整 |
| --- | ---: | ---: | ---: |
| 原问题文本 | 0.637 / 5 | 0.584 / 0 | 5/50 |
| 迁移后题目前显式加阶段提示 | 0.637 / 5 | 0.809 / 9 | 14/50 |
| 阶段通知作为一次 Add 写入，查询仍为原问题 | 0.637 / 5 | 0.576 / 0 | 5/50 |

原问题文本条件下，“迁移/旧字段可能失效”记忆卡在迁移后 20 题 **0/20** 进入 Top-5；显式阶段提示下为 **20/20**，完整覆盖配对改善 9 题、无回退。第三个条件把原生迁移通知文本作为一次 Add 写入后，通知本身在后 20 题 **12/20** 进入 Top-5，但更具体的迁移规则卡仍为 **0/20**，严格按知识依赖卡标签的完整覆盖也仍为 0。通知能提醒需要重新检查，并不等于已掌握迁移后的字段规则，因此单列而不冒充完整依赖命中。

报告在 `data/clbench-schema-proxy-50.json`、`data/clbench-schema-proxy-stage-cue-50.json`、`data/clbench-schema-proxy-persist-notice-50.json`，SHA-256 依次为 `d42834e2bd8077df3f67ddac72533dc903206e15488c06e62c3f719490b46dd2`、`f4721d41fc4c41a89249abe8037ab123eed93afb992f6c6f4f957159b9788adc`、`74ec69895f57bd917a43ec32f56573846c1cdd29a7108cddc6d681eab7fb86ab`；均记录数据、运行器与 `app/store.py` 哈希。

## 解释与下一步

原生 [task.py](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/database_exploration/task.py#L819)在阶段切换后给出一次“数据库可能变化”的通知，随后将其消费；第二条件给**全部**迁移后问题加提示，因此是状态已正确保留和注入查询时的乐观上界。第三条件更接近“通知进入历史、后续问题无提示”的 Add/Search 边界，但仍使用人工规则卡和公开依赖标签。三组都不是 CLBench 官方输入或评分器；这些数值不能映射到第四次 Smoke 的 G2/G4/F1。

可操作缺口是：仅用当前问题的词面检索无法稳定调用跨回合环境状态。下一步应先在真实 Add 历史中验证“阶段通知是否被写入、保留和检索”，再设计**通用的、由历史事件驱动**的当前状态提示或版本化规则索引；用公开跨阶段任务做答案与成本配对，同时守住已满分的 B/E/C3/G1 回归。不能把这个公开任务的固定阶段或正确答案硬编码进生产。
