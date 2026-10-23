# CLBench 公开 SQL 探索轨迹的阶段记忆代理（2026-10-22）

## 来源与边界

一手仓库 `pgasawa/continual-learning-bench@5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26` 隔离检出在 Git 忽略目录 `data/clbench-source/`。使用仓库自带 `final_results/runs/mem0-gpt-5.4/tasks/database_exploration.json.gz` 的五条公开运行轨迹，固定 SHA-256 `36afab46d4969ece1853c3fc8701d4014bfcf6a6f491f7670a67aeb1c7382e2a`。五条轨迹的 40 题、前 20/后 20 迁移安排相同，探索行为不同；它们是**相关的重复运行**，不能当成五套独立问题。

离线运行器 [probe_clbench_trace_memory.py](../benchmarks/probe_clbench_trace_memory.py) 按每条轨迹的 episode 顺序重放。第 `i` 题 Search 前，只把前 `i` 题真实 `QUERY` 的 SQL 与数据库 `observation` 成对写入 AML 的 `Add`；当前题及未来题的探索均在 Search **之后**写入。`ANSWER`、参考 SQL、金标答案、评分和 `knowledge_dependencies` 不进入 Add/Search。查询只用公开问题文本；第 21 题保留原生一次性迁移通知。`tables_involved` 只在返回后用于计算表观察覆盖，不能说明 SQL 答案正确。

代理指标：若当前题涉及的某张表在**同阶段的先前探索**中出现过，则将它视为可复用；检查 Top-5 是否含有该阶段该表的历史 SQL/观察。跨迁移旧阶段的同表结果另计“陈旧相关结果”。这比手写规则卡更接近真实经验，但仍不是 CLBench 原生 reward、准确率或查询成本，更不能映射到官方 G2/G4。

## 同题配对结果

| 公开轨迹 | 迁移前有可复用表的题 / 完整 Top-5 | 迁移后有可复用表的题 | 原版迁移后完整 Top-5 | 阶段优先完整 Top-5 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 16 / 7 | 17 | 0 | 10 |
| 1 | 15 / 4 | 17 | 2 | 7 |
| 2 | 15 / 5 | 17 | 5 | 13 |
| 3 | 16 / 7 | 17 | 5 | 9 |
| 4 | 17 / 6 | 17 | 0 | 15 |
| **合计** | **79 / 29** | **85** | **12** | **54** |

阶段优先实验在第 21 题把原生通知单独 Add，并将其后的探索归入新阶段。后续 Search 先取第四版原排序 Top-100，再稳定地把通知后观察置于前面，保持各组内部原顺序，最后取 Top-5；通知前探索仍可作为回退。基线与实验的 85 个迁移后可复用题逐题配对为 **42 改善、0 回退**，出现相关旧阶段结果的题数 **55→7**。迁移前不触发重排，79 个可复用题保持原指标。仅写入通知而不阶段重排时，轨迹 0 的迁移后完整 Top-5 仍为 0/17；对每题显式补阶段提示只到 2/17。轨迹 0 的原版 Top-100 已能完整找回同阶段表观察 15/17，说明主要缺口是排序。

这个实验识别的是**公开一次性通知的时间边界**，不读取参考答案或未来信息。当前离线适配器由轨迹明确标记通知所在 episode；生产候选需要从真实 Add 历史稳健识别一般性的规则/环境变更，不能硬编码第 21 题、固定文本或特定表名。阶段优先也可能把不相关的新观察压过仍有效的旧知识；必须用答案正确率、探索查询数和其他能力回归验证。

## 复现身份

命令示例：`py -3.13 -m benchmarks.probe_clbench_trace_memory --run-index 0 --output data/clbench-trace-final-run0-stage.json --persist-notice --prefer-current-stage`；省略末尾两个开关即为同轨迹基线。`--top-k 100` 可核对是否仅因前五条排序丢失。问题文件 `questions.json` 和 `questions_post_drift.json` 的 SHA-256 分别为 `452f1af2a4a24288b4d8ec4bda225c8e54ded359b82c119b6120b5ae0678c509`、`51109ae4f8be803b70cacd710d319e02b88d86a891ccd799f48cec8552bf711c`。

逐题报告及原始轨迹均保留在 Git 忽略目录 `data/`。五条基线报告 SHA-256：`d9f3554f40f84ad91b9572948fff7ca22953c21245a7cd9ca188fe47df5890be`、`5456c0cb26c53f910e45b1bb845ffa28c421b4c26c6a8aed08a4bb68efe908d1`、`53871fd47d5fc78c59b101328c32aca10d17ace5997f872f3dfe5361d5a0f1ec`、`ffcdbf505f9ecc380c24936fdd2e1e2b06588b7aafa04f7d0935297f2a15e3bb`、`01f94e2424705ddea39c92c552b1371c7d0dceeabd3c711adafb5cf6d42653ad`。五条阶段优先报告 SHA-256：`344dcca9db83fbb6a56bf6715c695a285d4d90ead4f546c867b758d08d63b6ec`、`9fb1439581a2ed9885f0fcb558c913ddb899928d57402c6de38ea3fedbf9e230`、`1ee819ed80f0c4cc30b6728dbf3381952ccfb118884969e580383f9f198dde25`、`fd3477fe6c6d1623c4a8bdb0121f908395aea08399305a6efe4a539832f0a323`、`e49e3fe2563a45eb04a4a2323466939f92d42272b6873395152f04b441b08678`。

## 下一步门禁

1. 实现与具体基准文本无关的环境/规则版本边界识别，先只在离线候选中启用；明确误触发与无通知的回退行为。
2. 在原生 CLBench 运行或等价的公开交互回放中，比较答案正确率和探索查询数；不能用表名命中代替 reward。
3. 用 LongMemEval、PersonaMem、本项目多跳/时序回归与 Railway Free 容量测试候选；无独立答案级净收益不部署、不发第五次 Smoke。

## 原生答案级运行准备（2026-10-22）

已在隔离检出的仓库用 `uv sync --no-dev --extra database_exploration` 安装本地环境，`clbench list` 能发现 `database_exploration`。LiteLLM 到本机 Ollama `qwen3-vl:4b-instruct` 的结构化 JSON 通路可调用，但一次简单示例返回的内容并不可靠；它最多可作同模型配对诊断，不能预测官方模型表现。该任务的 SQLite 实现不要求 Docker；本机 Docker daemon 当前未启动也不是这个任务的直接障碍。

原生数据库仓库 `continual-learning-bench/database-exploration@a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19` 公布 `products.db` 397,910,016 字节、LFS SHA-256 `edf8ee80ff125de0bfd6c37a1d185efa9e3037ce28eb1bd1d32ae0829bd264a6`，`products_drifted.db` 432,148,480 字节、LFS SHA-256 `a53d523f70604be0e4328f3722417895250ac35e1127cc504b609576aee70fad`。首次下载在缓存预分配后停滞，客户端把 `products.db` 标为完成，但实际 SHA-256 为 `ebf75abba86abb8bcfd7ec753db21ca951c785a8f70e25949a3975110e834e9d`，SQLite 打开返回 `file is not a database`；该无效文件已在忽略目录改名隔离为 `products.db.invalid-download`。第二个文件没有取得有效内容，直连公开 resolve URL 也超时。**原生答案/探索成本评测未运行**。下一次必须取得两份逐文件哈希吻合且 SQLite `quick_check` 通过的固定数据，再谈原生小样本。

## 通用通知边界识别的离线验证（2026-10-22）

在轨迹运行器中加入 `is_environment_change_notice`：仅接受至多 500 字符、`user` 角色、显式 `NOTICE`/`IMPORTANT`/`UPDATE` 类前缀，并同时含环境对象词及变更词的通知。词表不包含第 21 题、表名或原通知整句；实际通知仍按原生轨迹在迁移处一次性 Add，后续阶段由这条消息是否匹配决定，不再无条件递增。普通讨论、工具输出和与环境无关的通知有单元测试保护。

五条公开轨迹各检测到一次通知；重放后的 aggregate 和逐题 rows 均与原先手工阶段标记完全一致，包括迁移后同阶段可复用表 Top-5 完整覆盖 54/85。另以固定 LongMemEval 公开历史检查误触发：去重后 199,067 条消息中 0 条匹配。这只能说明该公开语料未见误触发；短通知格式外的真正环境变化可能漏检，恶意伪装通知也需防护。识别器仍仅在离线评测代码，未修改生产检索。2026-10-22 再试固定数据库的 Hugging Face 直连 HEAD，443 连接约 21 秒超时；原生答案级门禁仍不能运行。

## 原生数据库恢复与本地协议小样本（2026-10-23）

官方站点直连不可达后，经 `hf-mirror.com` 的固定 revision `a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19` 下载两份文件至 Git 忽略目录。`products.db` 为 397,910,016 字节、SHA-256 `edf8ee80ff125de0bfd6c37a1d185efa9e3037ce28eb1bd1d32ae0829bd264a6`；`products_drifted.db` 为 432,148,480 字节、SHA-256 `a53d523f70604be0e4328f3722417895250ac35e1127cc504b609576aee70fad`。两者均与一手仓库的 LFS OID 一致，且 SQLite `PRAGMA quick_check` 均为 `ok`。先前无效文件仍隔离为 `.invalid-download`，不参与运行。

在隔离 CLBench 仓库中创建仅用于**协议检查**的本地 2+2 迁移 schedule/variant，复用原生 task、两份固定 SQLite 与查询文件，固定本机 Ollama `qwen3-vl:4b-instruct`、ICL 系统。该小样本修改了题数，不是官方 20+20 schedule。每题查询预算 3 时，四题奖励均为 0；恢复原生预算 15 后，四题仍全错、奖励均为 0，分别使用 9、5、15、15 次探索。运行轨迹位于忽略目录 `data/clbench-source/results/database_exploration/traces/2026-10-23T10-02-32.275504Z/`。这证明数据和原生 QUERY/ANSWER 流程可执行，也表明当前本地回答器无辨别力；不能据此比较 AML 候选的答案增益，更不能映射官方 G2/G4/F1。

下一步需要能在原生小样本上取得非零基线的固定回答器，或一套同题、可审计的公开答案级交互回放。得到它后，再实现 AML 记忆对照，比较正确率、探索次数、迁移前后配对差异及跨任务回退。数据库下载阻塞已解除，回答器质量与 Railway 容量仍是独立门禁。

同机另试已安装的 `qwen3-vl:4b`（非 instruct）作为回答器，在原生结构化输出通路反复返回空 content，经过五次重试仍失败；已终止后续基线重试。它没有形成有效运行或分数，不作为候选比较。当前本机无其他已安装的更强回答模型，也未配置远程模型凭证。
