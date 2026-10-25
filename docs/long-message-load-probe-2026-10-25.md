# 长消息容量与延迟对照（2026-10-25）

目的：检查第四版词法路径在较长 Add 消息下的容量与 Search 延迟斜率。当前分支 `app/store.py` 比稳定提交 `c0001f84709ae134f3b5221574f3965f2f3f55c9` 多了默认关闭的可选 SQLite 压缩；本试验未启用压缩，也未改变线上服务。环境为 Windows Python 3.13，**不是** Railway Linux/cgroup 实测。合成填充文本重复固定规划短语，不代表公开数据分布或官方 Full 工作量。

同一运行器各建新库：500 次 Add × 每次 20 条、8 用户、8 Add worker；96 次 Search、32 Search worker、Top-100；`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`。两组仅改变每条消息追加的填充长度；负载和程序参数写入忽略版本控制的 JSON 报告。`benchmarks/run_load_test.py` 新增 `--message-padding-chars` 和完成时 `DB+WAL+SHM` 大小输出。

| 指标 | 原短消息 | 每条追加 900 字符 | 解释 |
| --- | ---: | ---: | --- |
| Add 错误 / Search 错误 | 0 / 0 | 0 / 0 | 合成负载均完成 |
| Search Top-1 命中 | 96/96 | 96/96 | 只检查人工代码字符串，非公开答案正确率 |
| Add p95 | 0.096 s | 0.103 s | 本机测量 |
| Search p95 | 0.789 s | 11.813 s | 约 15.0 倍，长消息已接近本地 15 s 门槛 |
| 进程峰值 RSS | 74,227,712 B | 117,047,296 B | 不含 Linux cgroup 页缓存 |
| 完成时 DB+WAL+SHM | 5,607,424 B | 41,791,488 B | 约 7.45 倍；未捕获并发期间存储瞬时峰值 |

报告 SHA-256：短消息 `D62DF3F3829DE0F75A7628EF18A810B9A0B02F6B1B61FE31FAACBD18FFEECFA9`，长消息 `24D7E749B328930010F37ABD9A6501E67F69869A9BC1E32E18652B3ADD8D5F43`。两份报告位于 `data/load-10k-{short,longpadding}-cache1-lexical-2026-10-25.json`。

一个 2 次 Add 的极小预检查曾因长文本的相邻上下文使 Top-1 失败；10,000 条正式配对中没有复现，不把它当成稳定回退。长消息结果显示延迟裕量明显缩小，但并不能证明 Railway 1 vCPU/512 MiB/500 MB 可以承载正式任务。Docker Desktop Linux 引擎启动后仍未提供 API socket，本轮无法运行同镜像 Linux 容器；正式容量门禁继续保持未通过。下一步应在可用 Linux 容器或 Railway 上按正式工作量与并发测 cgroup memory peak、`DB+WAL+SHM` 峰值、p95、错误率、冷启动与重启恢复。
