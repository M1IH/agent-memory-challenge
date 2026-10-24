# Railway Free 卷增长离线测量（2026-10-24）

本报告只使用已固定 SHA 的公开开发集历史，通过第四版不变的 `app/store.py`、`MemoryStore.add`、词法模式和 1 用户缓存写入本机临时 SQLite。未把问题、选项、参考答案、来源标注或 BEAM rubric 写入数据库。三个来源各用独立数据库；临时库在正常完成后移除。此测量不是官方 Full，也不是 Railway Linux 生产容量验收。

复现：

```powershell
py -3.13 -m benchmarks.probe_public_volume_growth --limit-messages 5000 --output data/public-volume-growth-5000.json
```

脚本 `benchmarks/probe_public_volume_growth.py` SHA-256：`c3c3971124fd422731e6eebbeff6f838cf0161b4f9fa25636382bf06142e6cb0`。原始 JSON 报告 `data/public-volume-growth-5000.json` SHA-256：`cba56899cfefd3c48b2c02946d98cfe441770d5b984102765ea5becaf5fd2ccc`。来源 SHA 全部写在脚本和 JSON 报告中，并由脚本在读取前核验。`app/store.py` 在当前 HEAD 与第四版 `c0001f84709ae134f3b5221574f3965f2f3f55c9` 的 Git blob 均为 `0199e8843bc840091917abec125618965dc0c4a4`。

| 公开开发集 | 写入消息 / 独立用户 | 输入 UTF-8 | SQLite 增量 | 扩张倍数 | 每条 SQLite 增量 | 500 MB 空卷估算 | 按 10/21 历史 65 MB 已用估算剩余 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LongMemEval-S | 5,000 / 10 | 4,759,651 B | 14,041,088 B | 2.950× | 2,808 B | 178,048 条 | 154,902 条 |
| PersonaMem-v1 32K | 5,000 / 30 | 4,237,569 B | 13,885,440 B | 3.277× | 2,777 B | 180,044 条 | 156,638 条 |
| BEAM 100K 对话 1–14 | 3,791 / 14 | 8,299,794 B | 18,866,176 B | 2.273× | 4,977 B | 100,470 条 | 87,409 条 |

实际采样的 `DB + WAL + SHM` 末值和峰值分别为 14,082,048、13,926,400、18,907,136 B；顺序 Add 后 WAL 均已自动归零。这里的峰值仅在每次 Add 完成后采样，不能覆盖并发请求中 WAL 暂时膨胀。`MemoryStore.add` 的 SQLite `content` 可包含上一条消息的上下文，`terms` 还保存词项副本，另有索引和元数据，因此观测到 SQLite / 原始 UTF-8 为 **2.273–3.277×**。容量估算按测得增量线性外推，只描述这些公开样本的消息量，不能换算为官方题目完成率或绝对上限；消息长度、数据集组合、SQLite 页与索引、现有旧数据、并发 WAL 和 Railway 文件系统都会改变结果。10/21 的 65 MB 已用不是实时读数。

[赛事页](https://agentmemoryleaderboard.ai/competition/)称文本赛道 6,000 余评测实例、32 个数据来源、总规模近 300M tokens；页面没有证明这 300M tokens 全部进入同一次 Full 的 Add 请求。公开 [API Guide](https://agentmemoryleaderboard.ai/api-guide)只定义 Add、Search 和 Health，并要求评测数据在任务结束后 30 天内删除，没有逐实例 Delete 调用。当前应用也只暴露 `/health`、`/add`、`/search`，`MemoryStore` 无逐实例清除路径，因此一旦数据写入同一卷，当前代码会累积到任务结束。

**条件风险量化：**若官网所称 300M tokens 全部成为同一次 Add 历史、平均至少形成 1 UTF-8 字节/token，且生产存储放大率不低于本次样本最小的 2.273×，则粗下界为约 **682 MB SQLite**，已超过 500 MB 卷；按 4 字节/token 的情景为约 2.73–3.93 GB。是否全部进入 Add、真实字节/token、是否有平台侧复用或分批，以及生产当前卷占用均未知，所以不能把这些情景写成确定的 Full 用量。若按旧 65 MB 已用，剩余约 435 MB；按 4 字节/token 情景，只有约 11–16% 的 300M tokens 能在该卷内持久化。这个门槛应在 Full 前用官网工作量说明和生产同构 Linux/线上容量复核，不应用短句 10k 压测替代。

下一步最短验证：先在 1 vCPU/512 MiB 的 Linux 容器上按当前词法配置回放公开长消息，并量 `DB+WAL+SHM`、cgroup RSS/OOM、Add/Search 延迟和重启恢复；再只读核对 Railway 当前卷实际余量、信用额度与正式部署身份。没有这些证据，Free 正式容量门禁保持未通过。
