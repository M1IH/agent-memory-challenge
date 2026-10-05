# 公开端到端评测登记表

> 首次核验：2026-10-04；最近核验：2026-10-05。仓库和许可证会变化；下载或发布适配器前必须重新核对。
> “仓库许可证”不自动等于“数据许可证”，两者都要有明确依据。

## 来源与数据许可已确认，固定文件门禁尚未完成

| 数据集 | 上游与核验版本 | 已确认许可 | 与本项目的价值 | 当前决定 |
| --- | --- | --- | --- | --- |
| LongMemEval | `xiaowu0162/LongMemEval@9e0b455f4ef0e2ab8f2e582289761153549043fc`；作者数据 `xiaowu0162/longmemeval-cleaned@98d7416c24c778c2fee6e6f3006e7a073259d48f` | 仓库 MIT；Hugging Face 数据卡明确标注 MIT、公开且非 gated | 500 道题；字段包含 `question_id/question_type/question/answer/question_date/haystack_session_ids/haystack_dates/haystack_sessions/answer_session_ids`，覆盖信息提取、多会话推理、知识更新、时序和拒答 | 首选候选，但尚未进入适配设计。必须先对固定 revision 的 `longmemeval_oracle.json`、`longmemeval_s_cleaned.json`、`longmemeval_m_cleaned.json` 验证下载并逐文件记录 SHA-256；之后才可按官方 evidence session/turn 标注设计适配，不得改写答案 |
| BEAM | `mohammadtavakoli78/BEAM@b2da22eac88bb0874c64665f13457eb99835774a`；作者数据 `Mohammadta/BEAM@3205395e897e7318c7b094ef4e6047b9b82dbb03` | 仓库 MIT；Hugging Face 数据卡明确标注 CC BY-SA 4.0、公开且非 gated | README 描述 2,000 道题及冲突、事件排序、更新、多会话、偏好、指令和时序能力；数据卡列出 `100K-00000-of-00001.parquet`、`500K-00000-of-00001.parquet`、`1M-00000-of-00001.parquet`，但本轮尚未核实 Parquet 实际字段 | 仅为部分核实候选，尚未进入适配设计。先验证最小文件下载、字段和 SHA-256；若采用固定子集，必须保存选择规则和样例 ID，并明确标为 BEAM 子集，不得称为完整 BEAM 成绩 |

## 条件可用，许可证或来源身份仍需确认

| 名称 | 当前证据 | 风险 | 当前决定 |
| --- | --- | --- | --- |
| LongMemEval-V2 | `xiaowu0162/LongMemEval-V2@2cc8c540bdb87fe6761629b585e727e1c4704520`；仅确认代码仓库 Apache-2.0 | 尚未核验作者数据地址、数据许可证、固定数据 revision 和可重复下载文件；451 道题、动态状态/工作流/环境陷阱等描述目前只作为仓库声明 | 第二阶段候选；在数据许可和固定文件完成核验前不下载、不适配、不引用结果 |
| LoCoMo-Refined | `mem-eval-suite/LoCoMo_refined@887091190789e8d6760e70b9edd696539923dc4f`；固定提交中的 `LICENSE.txt` 是 CC BY-NC 4.0，并提供 1,382 个问题及 Qwen3-14B judge | 非商业限制已确认；但奖金参赛和公开结果发布是否属于许可允许用途尚不能自行判定，仍需核对原始 LoCoMo 条款和必要时取得作者说明；官方 judge 对本项目约 100 元预算也过重 | 仅作为待确认候选，不下载、不进入首个适配器；即使获准使用，也必须保留官方 scorer 接口，不把自制 EM 冒充官方结果 |
| PersonaMem | GitHub 搜索只确认 `lmgyuan/personamem-website` 等展示/第三方仓库 | 尚未确认论文作者数据仓库、数据版本、许可证和稳定下载地址 | 暂不下载、不引用结果 |
| ScriptMem | 搜索得到 `memorax-ai/ScriptMem`，但 GitHub API 没有 SPDX 许可证信息 | 仓库描述、论文身份、数据文件与许可尚未确认 | 暂不下载、不引用结果 |
| CLBench | 以该名称搜索未找到可信的记忆评测官方仓库 | 可能是缩写歧义、论文未公开或名称写错 | 在确认论文全名和作者来源前排除 |

## 不采用的证据形式

- 第三方博客、排行榜截图或供应商复跑结果不能代替原始仓库、论文和数据卡。
- 没有明确许可的数据即使公开可访问，也不提交到本仓库。
- 超大集合的任意手挑样本不能称为该数据集的正式成绩；若使用固定子集，必须发布
  选择规则、样例 ID、版本和哈希，并标为代理评测。
- 依赖付费或超预算 LLM judge 的主指标必须同时保留低成本可复现指标，并单列运行成本。

## 下一次核验顺序

1. PersonaMem、ScriptMem 和 CLBench 的论文页面反向确认官方作者仓库。
2. LongMemEval 三个固定 JSON 的下载大小与逐文件 SHA-256；不提交原始数据。
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

