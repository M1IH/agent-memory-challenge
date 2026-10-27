# BEAM 轻量交叉编码重排探针（2026-10-27）

## 决策

**淘汰当前 Reranker 候选；不改生产、不部署、不建议第五次 Smoke。**它在固定 BEAM development 对话 1–2 的 4 道摘要题中，把标注来源完整进入 Top-100 从 0/4 提到 1/4；跨会话推理和知识更新各 3/4 持平。但同四道摘要题的固定本地 Qwen 4B 配对回答，经同一 rubric 代理后均值 **0.925→0.925**，逐题一改善、一回退、两题持平。没有答案级净提升，也没有跨来源无回退或 Railway Free 容量证明。

## 输入与实现

- 公开 BEAM 100K Parquet SHA-256 `c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace`；第四版 Top-300 排名报告 SHA-256 `14108a009a8538596e941c9b546a906f25739c4918fd89eca4e049479c4a29eb`。仅对前 2 段 development 对话的 12 题使用问题文本与已检出的 `role: content`，参考答案、rubric 和来源 ID 均不参与重排。
- 使用 FastEmbed `Xenova/ms-marco-MiniLM-L-6-v2` 交叉编码 Reranker；本地缓存 revision `a09144355adeed5f58c8ed011d209bf8ee5a1fec`，ONNX SHA-256 `c623d0bcb99f4622beb413eaef00cfbe5db20df9f1dd982da4b4f26022881870`。按模型分数降序、原排名破平，选前 100 条。
- [离线重排脚本](../benchmarks/probe_beam_cross_reranker.py) 当前 SHA-256 `62ca1a9ebaffd64c75456d515341cf2cc66d5622b725778530988843f5c6148f`；[答案输入转换](../benchmarks/prepare_beam_cross_answer.py) SHA-256 `c9fb3d4c7a32cc4a8bb83de374b25e64547ba73a8fd39ca823fd2bca36bf6489`。初次 12 题运行以 batch 16、单线程完成约 379.6 秒，逐题报告 `data/beam-cross-reranker-dev2-2026-10-26.json` SHA-256 `ad0955c380fb7a16e07ab2266303c749d77382beb9e634cf7d2447d6b71ac773`。
- 一道固定摘要题改用 batch 1、单线程时耗时 22.57 秒，来源结论与 batch 16 相同；报告 SHA-256 `cc430305d17a6363c82f60375516e8c779ef15b1e5c2294e3d0a7fad77180832`。Windows 实测工作集约 355–360 MB；batch 16 的进程工作集约 1.27 GB。它不是 Linux cgroup 峰值或 16 路正式 Search 容量验收。

复现命令（固定公开数据和模型文件须先校验上述哈希）：

```powershell
py -3.13 -m benchmarks.probe_beam_cross_reranker --development-conversations 2 --threads 1 --batch-size 16 --output data/beam-cross-reranker-dev2-2026-10-26.json
py -3.13 -m benchmarks.prepare_beam_cross_answer --reranked data/beam-cross-reranker-dev2-2026-10-26.json --output data/beam-cross-answer-evidence-dev2-2026-10-26.json
py -3.13 -m benchmarks.run_beam_local_answerer --retrieval-report data/beam-cross-answer-evidence-dev2-2026-10-26.json --category summarization --limit 4 --output data/beam-cross-local-answer-dev2-2026-10-26.json
py -3.13 -m benchmarks.score_beam_local_answers --answers data/beam-cross-local-answer-dev2-2026-10-26.json --output data/beam-cross-local-rubric-dev2-2026-10-26.json
```

用 `benchmarks/run_beam_local_answerer.py` 的固定 24,000 字符、每条 1,600 字符、8K 上下文、温度 0 配对答题；再由 `benchmarks/score_beam_local_answers.py` 加载公开 rubric 后验评分。答案输入报告、逐题回答、rubric 报告在忽略目录 `data/`，SHA-256 分别为 `c5945cf2758249dc699a8ab9724ea8ba77a60a7fc169460446e8ff34b1775b67`、`6bc13751ed7f5d14dceb7ff2656c50c6d39270fb49e9df8f276f4b89ad9ce77c`、`1b238961413e3c2e14613d8dbd939507f35e25c10dd7c457db1d4b7616d0b144`。四题 rubric 逐题为 **0.7→0.9、1.0→0.8、1.0→1.0、1.0→1.0**。本地同模型 rubric 有波动，不能当成 BEAM 作者或 AML 官方成绩；但这组配对没有支持发布所需的净增益。

尝试扩到第 4 段对话时，旧 Top-300 报告把一条切块后的超长消息只记录为原消息 ID；当前脚本按完整原消息重建，长度校验失败并停止，未形成第 3–4 段的完整结果。当前重排脚本把可复现范围显式限定为前 2 段，不把失败运行计入收益或回退。若将来有独立答案级收益再重开该路线，应先让检索报告保存精确片段 ID，并在 1 vCPU/512 MiB Linux 上检验冷加载、16 路并发与延迟。
