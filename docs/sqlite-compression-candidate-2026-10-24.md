# SQLite 文本压缩容量候选（2026-10-24，未发布）

## 结果与决定

在第四版词法配置、固定公开开发历史和相同 `MemoryStore.add` 流程下，离线选择性压缩 SQLite 的 `content` 与 `terms` 字段，5,000 条写入样本的数据库增量下降 **44.1%–50.8%**。LongMemEval 前 30 道 development 题的完整 Top-100 来源序列与未压缩版 **30/30 完全相同**；本地相关 262 项测试通过，Ruff 通过。压缩由构造参数 `compress_text=False` 默认关闭，生产未改、未部署。

| 公开开发来源 | 未压缩 SQLite 增量 | 压缩后 SQLite 增量 | 降幅 |
| --- | ---: | ---: | ---: |
| LongMemEval-S，5,000 条 | 14,041,088 B | 7,852,032 B | 44.1% |
| PersonaMem-v1，5,000 条 | 13,885,440 B | 7,692,288 B | 44.6% |
| BEAM 100K 对话 1–14，共 3,791 条 | 18,866,176 B | 9,281,536 B | 50.8% |

这些降幅是本机 Windows SQLite 文件实测，不是 Railway Linux 卷验收。30 题来源完全相同只证明该小集合的压缩解码等价，不能证明答案级净提升；压缩是容量候选，**不能单独触发第五次 Smoke**。

## 风险与门禁

1. 旧版代码无法可靠读取新写入的压缩 BLOB；启用后不能简单回滚到第四版二进制而保留同一数据库。必须先设计并验证可逆迁移或独立备份恢复，不能直接在生产开关。
2. 旧行保持文本，新行可为 BLOB。混合读取、跨实例重开、用户隔离的本地测试已覆盖；还缺正式长历史的跨能力 Top-100/答案级回退、并发 Add/Search p95、CPU、cgroup RSS、WAL 峰值和重启恢复。
3. 按官网近 300M tokens 的条件情景，即使约减半，500 MB 卷仍可能不足；实际 Full Add 量未知。压缩也不解决 Free `$0.85/$1.00` 额度、模型资格和材料绑定问题。

## 可复核数据

固定来源校验沿用 `benchmarks/probe_public_volume_growth.py`；压缩空间上限探针为 `benchmarks/probe_volume_compression.py`。报告均在 Git 忽略的 `data/`：

| 报告 | SHA-256 |
| --- | --- |
| `public-volume-growth-5000-compressed.json` | `f56c6861260ba19221e1e242f7cf7464c852c1d1e912730f5a74b74b9ee2f20e` |
| `volume-compression-1000.json` | `a58b24b0224c9aa397d2e0feeadc0e8acb426fe5905ce287f749357f2d15b81d` |
| `compression-retrieval-baseline-30.json` | `5355d16e38fe9ec191b6fef7eed963ec3b37964cfc5d47eb8a9e1a4ef31a171f` |
| `compression-retrieval-candidate-30.json` | `5be6ab8a7c842b9ac0a6b5b1a1bef05e91109eb4711eab56641699477564f16d` |

下一步仅在确定正式 Full 工作量与预算有足够余量后考虑继续压缩迁移；否则应优先提交已验证第四版和解决服务容量。不得把此容量改动写成官方分数提升。
