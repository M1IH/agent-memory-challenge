# 公开端到端评测登记表

> **2026-10-20 实施更新：**LongMemEval-S cleaned 的固定 277,383,467 字节文件已按 revision `98d7416c24c778c2fee6e6f3006e7a073259d48f` 下载并核对 SHA-256，来源清单见 `benchmarks/longmemeval-s-source.json`，纯格式适配器见 `benchmarks/adapt_longmemeval.py`。完整 500 题标准化已通过；当前表格中“尚未进入适配设计”是历史状态。真实检索与最终答题基线尚未完成。

> 首次核验：2026-10-04；最近核验：2026-10-05。仓库和许可证会变化；下载或发布适配器前必须重新核对。
> “仓库许可证”不自动等于“数据许可证”，两者都要有明确依据。

## 来源与数据许可已确认

| 数据集 | 上游与核验版本 | 已确认许可 | 与本项目的价值 | 当前决定 |
| --- | --- | --- | --- | --- |
| LongMemEval | `xiaowu0162/LongMemEval@9e0b455f4ef0e2ab8f2e582289761153549043fc`；作者数据 `xiaowu0162/longmemeval-cleaned@98d7416c24c778c2fee6e6f3006e7a073259d48f` | 仓库 MIT；Hugging Face 数据卡明确标注 MIT、公开且非 gated | 500 道题；字段包含 `question_id/question_type/question/answer/question_date/haystack_session_ids/haystack_dates/haystack_sessions/answer_session_ids`，覆盖信息提取、多会话推理、知识更新、时序和拒答 | 首选候选，但尚未进入适配设计。必须先对固定 revision 的 `longmemeval_oracle.json`、`longmemeval_s_cleaned.json`、`longmemeval_m_cleaned.json` 验证下载并逐文件记录 SHA-256；之后才可按官方 evidence session/turn 标注设计适配，不得改写答案 |
| BEAM | `mohammadtavakoli78/BEAM@b2da22eac88bb0874c64665f13457eb99835774a`；作者数据 `Mohammadta/BEAM@3205395e897e7318c7b094ef4e6047b9b82dbb03` | 仓库 MIT；Hugging Face 数据卡明确标注 CC BY-SA 4.0、公开且非 gated | README 描述 2,000 道题及冲突、事件排序、更新、多会话、偏好、指令和时序能力；数据卡列出 `100K-00000-of-00001.parquet`、`500K-00000-of-00001.parquet`、`1M-00000-of-00001.parquet`，但本轮尚未核实 Parquet 实际字段 | 仅为部分核实候选，尚未进入适配设计。先验证最小文件下载、字段和 SHA-256；若采用固定子集，必须保存选择规则和样例 ID，并明确标为 BEAM 子集，不得称为完整 BEAM 成绩 |
| PersonaMem | `bowen-upenn/PersonaMem@d07e6ade22e85e0e5d562247323a9c3e07553226`；作者数据 `bowen-upenn/PersonaMem-v1@a8076d5608c93ba2a28983cd78aa99b01a163ae7` | 代码仓库 MIT；Hugging Face 数据卡明确标注 MIT、公开且非 gated | 作者 README 说明公开问题、答案、上下文和元数据；固定数据 revision 含 32K/128K/1M 三档的 `questions_*.csv` 与 `shared_contexts_*.jsonl`。32K 上下文文件约 5.6 MB，适合下一轮低成本字段与适配边界核验 | 可进入第二个适配器的固定文件门禁。先只下载 32K 档，记录逐文件 SHA-256 并确认问题与共享上下文的连接键；不得把 v2/v3 混入 v1 结果 |

## 条件可用，许可证或来源身份仍需确认

| 名称 | 当前证据 | 风险 | 当前决定 |
| --- | --- | --- | --- |
| LongMemEval-V2 | `xiaowu0162/LongMemEval-V2@2cc8c540bdb87fe6761629b585e727e1c4704520`；仅确认代码仓库 Apache-2.0 | 尚未核验作者数据地址、数据许可证、固定数据 revision 和可重复下载文件；451 道题、动态状态/工作流/环境陷阱等描述目前只作为仓库声明 | 第二阶段候选；在数据许可和固定文件完成核验前不下载、不适配、不引用结果 |
| LoCoMo-Refined | `mem-eval-suite/LoCoMo_refined@887091190789e8d6760e70b9edd696539923dc4f`；固定提交中的 `LICENSE.txt` 是 CC BY-NC 4.0，并提供 1,382 个问题及 Qwen3-14B judge | 非商业限制已确认；但奖金参赛和公开结果发布是否属于许可允许用途尚不能自行判定，仍需核对原始 LoCoMo 条款和必要时取得作者说明；官方 judge 对本项目约 100 元预算也过重 | 仅作为待确认候选，不下载、不进入首个适配器；即使获准使用，也必须保留官方 scorer 接口，不把自制 EM 冒充官方结果 |
| ScriptMem | 作者仓库 `memorax-ai/ScriptMem@831ca3e3123dbaed53fdf7d80fde066bed9f5abc`；README 与 `LICENSE.txt` 明确为 CC BY-NC 4.0 | 公开材料只有 457 道题、选项、答案、元数据和评测代码；README 明确说明四部影视作品的原始剧本/对话因版权原因没有发布，`conversation` 仅保留省略说明与合成结构示例 | 排除出当前 Add/Search 端到端检索集：缺少可加入记忆库的来源对话，无法做忠实的纯格式适配；也不以题目或答案反推上下文 |
| CLBench | 一手仓库 `pgasawa/continual-learning-bench@5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26`，论文 arXiv `2606.05661`；仓库 Apache-2.0 | 它是跨多 episode 的容器化交互环境与在线学习基准，要求 Python 3.13、uv、Docker 和任务环境；并非可直接映射为 Add 历史 + Search 证据的静态文本 QA 数据集 | 确认来源后排除出当前文本检索适配器范围。若未来评估完整 agent 的持续学习能力，应作为独立实验轨道，不能把环境轨迹强行转换后称为 CLBench 正式成绩 |

## 不采用的证据形式

- 第三方博客、排行榜截图或供应商复跑结果不能代替原始仓库、论文和数据卡。
- 没有明确许可的数据即使公开可访问，也不提交到本仓库。
- 超大集合的任意手挑样本不能称为该数据集的正式成绩；若使用固定子集，必须发布
  选择规则、样例 ID、版本和哈希，并标为代理评测。
- 依赖付费或超预算 LLM judge 的主指标必须同时保留低成本可复现指标，并单列运行成本。

## 下一次核验顺序

1. 核对并恢复当前分支缺失的 LongMemEval 固定文件哈希、下载清单和首个适配器产物；在产物可审计前不继续切分。
2. PersonaMem-v1 32K 档两个固定文件的实际字段、连接键、下载大小与逐文件 SHA-256；不提交原始数据。
3. BEAM 最小规模文件的实际字段、下载大小与逐文件 SHA-256；不提交原始数据。
4. LoCoMo-Refined 的原始 LoCoMo 条款，以及 CC BY-NC 4.0 对奖金参赛用途的适用性。

## 官方模型规则：2026-10-05 实时核验

- 赛事 FAQ 的“学术榜可以使用哪些模型”写明：Embedding 必须使用
  `text-embedding-v4`，LLM 相关组件必须使用 `gpt-4o-mini`，Reranker 不限制；使用
  自训练或其他开放权重模型的系统建议参加工业榜。
- 同日 `/rules` 与 `/api-guide` 的 Full 检查项写的是：Open-source Methods 在 Add
  阶段预计使用 `gpt-4o-mini`，Commercial Products 没有 Add/Search 模型限制。
- 参赛说明又把当前组别称为“开源方法榜 / 商业产品榜”，没有明确定义“学术榜”是否
  等同于“开源方法榜”。因此不能自行认定本地 BGE 符合奖金所在的开源方法榜，也不能
  只凭页面差异立即重构生产系统。
- 在主办方书面确认适用范围前，模型合规状态标记为 **P0 待确认**；不得用当前 BGE
  版本启动新的正式评测。需要确认的问题是：文本开源方法榜是否强制在 Add/Search
  使用 `text-embedding-v4`；`gpt-4o-mini` 是仅限 Add 中的 LLM 组件，还是所有参赛方
  LLM 相关组件；纯检索系统是否需要调用该 LLM。

实时来源：

- <https://agentmemoryleaderboard.ai/competition/>
- <https://agentmemoryleaderboard.ai/rules>
- <https://agentmemoryleaderboard.ai/api-guide>
- <https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned>
- <https://huggingface.co/datasets/Mohammadta/BEAM>

