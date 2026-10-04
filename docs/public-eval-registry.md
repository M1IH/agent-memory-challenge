# 公开端到端评测登记表

> 首次核验：2026-10-04。仓库和许可证会变化；下载或发布适配器前必须重新核对。
> “仓库许可证”不自动等于“数据许可证”，两者都要有明确依据。

## 已确认，可进入适配设计

| 数据集 | 上游与核验版本 | 已确认许可 | 与本项目的价值 | 当前决定 |
| --- | --- | --- | --- | --- |
| LongMemEval | `xiaowu0162/LongMemEval@9e0b455f4ef0e2ab8f2e582289761153549043fc` | 仓库 MIT；README 指向作者 Hugging Face 清洗数据 | 500 道题，覆盖信息提取、多会话推理、知识更新、时序和拒答；结构最接近 Add 历史 + Search 证据 + 固定回答器 | 第一优先适配。先核验 Hugging Face 数据卡许可与文件哈希，再做小规模 development/frozen 切分 |
| LongMemEval-V2 | `xiaowu0162/LongMemEval-V2@2cc8c540bdb87fe6761629b585e727e1c4704520` | 仓库 Apache-2.0 | 451 道题，包含动态状态、工作流、环境陷阱和前提意识；规模可到 115M tokens | 作为第二阶段压力与代理记忆能力验证，暂不作为首个适配器 |
| BEAM | `mohammadtavakoli78/BEAM@b2da22eac88bb0874c64665f13457eb99835774a` | 仓库 MIT；数据许可仍需单独核验 | 2,000 道题，覆盖冲突、事件排序、更新、多会话、偏好、指令和时序；128K 到 10M tokens | 能力覆盖强，但完整运行超出当前 Railway 资源；先核验数据卡，再选择许可允许的 128K 固定子集 |

## 条件可用，许可证或来源身份仍需确认

| 名称 | 当前证据 | 风险 | 当前决定 |
| --- | --- | --- | --- |
| LoCoMo-Refined | `mem-eval-suite/LoCoMo_refined@887091190789e8d6760e70b9edd696539923dc4f`；README 声称 CC BY-NC 4.0，并提供 1,382 个问题及 Qwen3-14B judge | GitHub API 未识别 SPDX；需要直接核对 `LICENSE.txt`、原始 LoCoMo 条款和数据再分发限制；官方 judge 对本项目约 100 元预算过重 | 核实许可后可用作高价值发展集；评分先保留其官方 scorer 接口，不把自制 EM 冒充官方结果 |
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

1. LongMemEval Hugging Face 数据卡、文件列表、许可和不可变 revision。
2. LoCoMo-Refined 的 `LICENSE.txt`、数据字段和 judge 许可/资源要求。
3. BEAM Hugging Face 数据卡与 128K 文件规模。
4. PersonaMem、ScriptMem 和 CLBench 的论文页面反向确认官方作者仓库。

