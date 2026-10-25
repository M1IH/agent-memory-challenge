# LongMemEval 公开无答案题诊断（2026-10-25）

固定 LongMemEval-S 规范化集的记录 ID 含 `_abs` 后缀者共 30 题，其中 development 27 题、frozen holdout 3 题。本轮只使用 27 道 development 题。`_abs` 是公开记录的无答案子集标记，**不是**数据集的能力标签，也不能直接映射到 AML 官方 H2。参考答案通常说明相关事实存在，但问题要求的主体、对象、地点或数量并未得到支持。

检索基线 `data/longmemeval-s-dev-lexical-390.json` 中，27 题的标注来源进入 Top-1/Top-5/Top-100 分别为 16/22/27；这些来源常是用于识别事实不充分的邻近信息，**不能把命中率当作无答案正确率**。例如“仓鼠叫什么”返回猫的对话、“在韩国待多久”返回日本旅行的对话。

固定本地回答器 `qwen3-vl:4b-instruct`、digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`，第四版词法 Top-5，8K 上下文，temperature 0、seed 0，给出公开 `source_question_date_text`，27 题逐题只作答一次；运行命令：

```powershell
& 'C:\Users\OTTO\anaconda3\python.exe' -m benchmarks.run_longmemeval_local_answerer --output data/longmemeval-s-dev-abstention-time-answerer-27.json --per-capability 100 --case-id-suffix _abs --top-k 5 --skip-without --include-query-time
```

报告 SHA-256 为 `796d6ac75b1512c1333f594414b4d549f4493283a4c27e21488ad0408aa032ae`。23/27 题短答为“I don't know”。其余四题逐题复核：番茄/辣椒题指出已知 5 株番茄但没有辣椒数量，属于**部分事实且未给出不可支持的总数**；三题明显越界，分别凭无关上下文回答“Harvard University”、断言 Alex 比 Tom 先成为父母、把 Harajuku 的居住时间套给 Shinjuku。参考答案为解释性长句，当前严格字面评分 `0/27` 完全不能反映上述差异，不得写作 0% 无答案能力。

第一次没有传提问日期的对照是 22/27 回答“I don't know”；补日期后为 23/27，其中《Sapiens》剩余页数题从臆算变为弃答，Shinjuku 题仍错误且臆算时长改变。结论限定于这个本地 4B 回答器、Top-5 和公开 development 子集；官方统一回答器与 Top-100 上下文不同，无法推断 H2 分数或第五版收益。下一步若改 Search，须以不使用参考答案的通用证据充分性判别为候选，在这些题与有答案配对题同时做答案级对照，并保护 B/E/C3/G1；不能直接按 `_abs` 后缀或已见问题加规则。

**Top-20 单变量对照（2026-10-26）：**保持相同模型、日期提示和 8K 上下文，只将检索深度改为 20；报告 SHA-256 `bcc5aebee7b6697f547ce687f392c28e2a92f7f60523353c694185080d1d2fd3`。逐题比较发现 Shinjuku 题从臆算 7 个月改为弃答，但机场巴士节省额题从弃答变为臆测 `$40–$60`，经理带队人数题从弃答变为断言 4 人；Harvard 与 Alex 的无依据断言仍在。部分回复虽然不以“I don't know”开头，实际也表达信息不足，因此不能用开头字串的 23→18 变化直接算正确率。增加证据深度未形成稳定改善，并可能在本地 8K 窗口引入更多截断或干扰；不作为生产 Top-K 调整依据。
