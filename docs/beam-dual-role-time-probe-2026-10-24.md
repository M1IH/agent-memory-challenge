# BEAM 双角色时间覆盖卡离线实验（2026-10-24）

## 决策

**淘汰时间覆盖卡候选，不修改生产、不发起第五次 Smoke。**固定公开 BEAM 作者数据的 development 对话 1–14 上，摘要题完整原消息来源进入 Top-100 为第四版 3/28、候选 1/28。固定本地 Qwen 4B 配对答题并用同模型 rubric 代理后验评分，28 题均值为第四版 **0.5554**、候选 **0.4961**；8 题改善、9 题回退、11 题相同。这个本地代理分数不是 BEAM 作者或 AML 官方分数，且同模型自评存在不稳定性；它足以否决该候选，不能证明第四版的官方 F1 成绩。

## 方法与限制

- 输入仅为固定 BEAM 100K Parquet 的 `chat` 历史，问题只用于检索；rubric、答案及所需消息 ID 不进入索引、卡片或答题器。开发对话 1–14；15–20 未触碰。
- 对话按批次及角色生成有界、抽取式时间覆盖卡；Top-100 保留相同返回条数和不增的字符预算。卡片只能算部分呈现；**不计为原消息完整证据**。
- 同一回答器、模型 digest、系统提示和 24,000 字符证据预算对第四版及候选逐题配对。rubric 仅在答案文件落盘后加载；评分为本地 Qwen 同模型代理。
- 最先 4 题重新评分时，基线均值从先前一次的 0.9167 变为 1.0000，候选两次均为 0.8750。汇总采用此次 4 题评分与余下 24 题评分，明确该代理并非完全确定。余下 24 题基线 0.4813、候选 0.4330。
- BEAM 来源覆盖、字符预算和本地 rubric 都无法直接映射官方 F1。未运行跨能力公开答案级回退或 Railway Free 正式容量，因为本候选已在第一门禁失败。

## 可复现依据

脚本：`benchmarks/probe_beam_dual_role_index.py`、`benchmarks/run_beam_local_answerer.py`、`benchmarks/score_beam_local_answers.py`。固定原始 Parquet SHA-256 `c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace`。被 Git 忽略的逐题报告与 SHA-256：

| 报告 | SHA-256 |
| --- | --- |
| `data/beam-dual-role-time-dev14.json` | `2feca3f0521629d21362aa7ed2ae7ac7aef1bce3df7c1ada96f7056c762b8c4a` |
| `data/beam-dual-role-time-local-answer-4.json` | `77c56a8f8336a5ee3e0f9245a28f0f8a6ff2a2b4a99eeca0478bc71af4a0d243` |
| `data/beam-dual-role-time-local-answer-remaining24.json` | `183cea221657665c87d492ff553439a90443f6d3dbe3582e11b7829911ef79c1` |
| `data/beam-dual-role-time-local-rubric-4.json` | `5d94cfbbb2408bb5fd51331afd9d9f11db510c58454d5a0498be775621d3af24` |
| `data/beam-dual-role-time-local-rubric-remaining24.json` | `a92694b596edcef48e53821161fd438e02f4014c1975afc99de2147b8e325d09` |

另两个离线变体也未通过来源门禁：完整原文提权将摘要完整 Top-100 从 3/28 降到 2/28；查询相关短摘卡降到 1/28。时间覆盖卡同样降到 1/28，跨会话推理 11/28、知识更新 22/28 均与第四版持平。三者都不能作为全局摘要修复。

## 下一动作

停止此压缩卡方向的扩参。将剩余时间优先用于第四版参赛材料、正式写入量与 Free 卷/RSS 核验、模型规则澄清及服务连续性；只有出现独立公开答案级净收益且跨能力无关键回退的新候选，才重新打开第五次 Smoke 决策。
