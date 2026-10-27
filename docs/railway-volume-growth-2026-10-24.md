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

## 扩大到 20,000 条的线性复核

2026-10-24 再以同一脚本、固定来源和独立数据库运行 `py -3.13 -m benchmarks.probe_public_volume_growth --limit-messages 20000 --output data/public-volume-growth-20000.json`。报告 SHA-256 `2a9de755b5da58a7792134079a54ab807c7c1f669bce35ee60373fb4bd261d48`。BEAM development 仅有 3,791 条，因此其结果与上表相同。

| 公开开发集 | 5,000 条放大率 | 20,000 条放大率 | 20,000 条 DB+WAL+SHM 采样峰值 | 20,000 条每条 SQLite 增量 |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval-S | 2.950× | 2.888× | 56,197,120 B | 2,807.8 B |
| PersonaMem-v1 32K | 3.277× | 3.440× | 55,521,280 B | 2,774.0 B |

两组在 5,000→20,000 条时每条数据库增量基本稳定，未发现能把 500 MB 卷风险解释为小样本固定开销的证据。20,000 条仍远小于官网所述总 token 规模；它也不证明正式 Full 全量 Add、Linux cgroup RSS、并发 WAL 或线上余额。Railway 控制台同日确认 Free 当前用量约 `$0.85/$1.00`、卷 **Max 500 MB**；卷曲线没有可读精确值。Linux Docker daemon 当前未运行，正式容量门禁继续保持未通过。

## 2026-10-26 存储字段拆解

在同一固定公开历史和未压缩词法配置下，给[容量脚本](../benchmarks/probe_public_volume_growth.py)增加 SQLite `LENGTH(CAST(... AS BLOB))` 汇总，再跑 5,000 条上限（BEAM 仅 3,791 条）。这些是各列负载的 UTF-8/BLOB 字节总和，**不能与 SQLite 文件大小简单相加**，因为文件还包含行、页和索引开销。

| 来源 | SQLite 增量 | `content` 字节 | `terms` 字节 | 两列合计占增量约 |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval-S | 14,041,088 | 5,305,803 | 4,927,945 | 72.9% |
| PersonaMem-v1 | 13,885,440 | 4,338,680 | 4,254,554 | 61.9% |
| BEAM 100K | 18,866,176 | 8,331,011 | 7,058,715 | 81.6% |

三组的 `embedding` 字节均为 0，符合当前词法配置。输入 UTF-8 分别为 4,759,651、4,237,569、8,299,794 字节；两列重复保存展示文本与词项确实是主要容量来源，`terms` 单列与 `content` 同量级。固定报告 `data/public-volume-growth-5000-columns-2026-10-26.json` 的 SHA-256 为 `3a06b506bd2fd68072a6f2e425dbb4e2a29d8bbb157e2a18207bb890b7089f22`，运行脚本 SHA-256 为 `70d7512b5df0bf433bafc7f1cb8603c7a3dc82dcd192482f52bc8d3a66b616f3`；报告位于 Git 忽略的 `data/`。此拆解解释压缩实验的空间收益，却没有解除旧版读取压缩 BLOB 的回滚缺口，也没有证明 Railway 500 MB 能容纳正式 Full。容量改动继续保持离线，不能作为第五次 Smoke 得分候选。

## 2026-10-27 扩至公开历史上限

同一脚本、固定来源及 SHA 校验，运行 `py -3.13 -m benchmarks.probe_public_volume_growth --limit-messages 100000 --output data/public-volume-growth-100000-2026-10-27.json`。忽略目录中的报告 SHA-256 为 `f24439b9768dbc3e425272d2bfc44da96d4ebbcd596fc3258db425e0e44af853`。LongMemEval-S development 实际写满 100,000 条、203 用户、9,744 次 Add，SQLite 文件为 **283,553,792 B**，输入 UTF-8 98,851,953 B，净增 283,512,832 B，放大率 **2.868×**，每条净增 2,835 B。PersonaMem development 在 68,522 条耗尽，文件为 **196,825,088 B**；BEAM 仍仅 3,791 条。抽样点上的 WAL 均为 0，不能据此推断并发 Add 的瞬时峰值。

若把 LongMemEval 这 10 万条额外写入 10 月 27 日仍占 **63.414272/500 MB** 的生产卷，按十进制 MB 合计约 **346.97 MB**，名义剩余约 **153.03 MB**。这只证明该公开样本的离线存储量落在卷额度内；官方 Full 的总 Add 数、消息长度与重用模式未知，且本机顺序写入没有覆盖 Railway 的文件系统、并发 WAL、cgroup 或持续费用。因此正式容量门禁仍未通过，不能把 10 万条样本外推成 Full 可承载声明。
