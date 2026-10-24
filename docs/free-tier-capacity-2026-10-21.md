# Railway Free 容量诊断（2026-10-21）

## 线上状态

Railway CLI 显示第四版 deployment `e42eb7f9-bf7f-4863-be1b-a425df6e7832`、原 `/data` 卷约 63/500 MB，服务处于 `Sleeping`。访问生产 `/health` 后返回 `ok`，本次冷启动墙钟时间约 7.8 秒。单次健康成功不证明评测期间持续在线或并发容量。

后续只读核对生产变量的非秘密设置：`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`，缓存字节预算未显式设置，代码默认 64 MiB。Railway 最近 1 小时的资源摘要为内存峰值 86 MB、卷使用约 65/500 MB；该窗口仅包含轻量请求，不是 10k 正式负载。**下述 BGE 两次测试并非当前生产配置同构测试。**

## 本机同规模负载对照

当前开发分支的 `app/` 与第四版生产提交一致（`git diff c0001f8 HEAD -- app` 为空）。三次运行均为 Windows 本机 Python 3.13、10,000 条记忆、8 用户、500 个 Add 请求（每次 20 条）、8 个 Add worker、96 个 Search 请求、32 个 Search worker、Top-K 100。门禁设为 RSS 峰值不超过 524,288,000 字节、Add p95 不超过 45 秒、Search p95 不超过 15 秒。每次均重新建库，不在生产环境注入测试数据。

| 设置 | 峰值 RSS | 524.3 MB 阈值 | Add p95 | Search p95 | 正确与隔离 |
| --- | ---: | --- | ---: | ---: | --- |
| 当前生产同构设置：词法检索、1 用户缓存 | 72,757,248 字节 | 本机通过，余 451,530,752 字节 | 0.13 秒 | 0.91 秒 | 96/96 Top-1，0 错误，0 泄漏 |
| 假设启用 BGE、默认缓存关闭 | 540,237,824 字节 | 失败，超 15,949,824 字节 | 7.73 秒 | 3.53 秒 | 96/96 Top-1，0 错误，0 泄漏 |
| 假设启用 BGE、4 用户缓存、64 MiB 快照预算 | 440,303,616 字节 | 本机通过，余 83,984,384 字节 | 7.52 秒 | 2.90 秒 | 96/96 Top-1，0 错误，0 泄漏 |

逐项原始报告保存在被 Git 忽略的 `data/`：当前生产同构设置 `load-10k-free-current-lexical-2026-10-21.json`，SHA-256 `c1a1517ad8517286e4dbfe368ad247bbd6cab288a720715cd53f347319d993dd`；假设 BGE 缓存关闭 `load-10k-free-cap-2026-10-21.json`，SHA-256 `d8015d9c851977ea8698aedd9a1dba5338368712841546190eefe0223f9c9dde`；假设 BGE 缓存 4 用户 `load-10k-free-cap-cache4-2026-10-21.json`，SHA-256 `11be37a04198b89755707c74ec03d742c530a0396692a8f14b0081612eebe26b`。BGE 缓存测试统计：28 次命中、51 次并发等候复用、25 次加载、21 次淘汰；结束时 4 用户快照估算占 19.2 MB。

## 决策

当前词法生产配置在 Windows 本机同规模负载下留有较大内存余量；BGE 两次是未来可能启用 embedding 时的条件实验，不能据此说当前生产超限，也无需为了当前容量把缓存从 1 改为 4。Windows 进程 RSS 不是 Railway Linux 容器的峰值。生产仍需核验实际 RSS、重启后缓存冷加载、Top-100 并发、延迟、持久卷增量和 Sleeping 冷启动；若容器超限或冷启动影响评测，应调整资源档位或部署策略。当前不把本机通过写成正式容量门禁通过，也不据此发起第五次 Smoke 或 Full。

## 2026-10-24 线上复核

长时间空闲后生产 `/health` 返回 HTTP 200 用时 7.67 秒，紧接的热请求 HTTP 200 用时 0.79 秒；再次观察到 Sleeping 冷启动延迟。Railway CLI `whoami` 与 `status --json` 仍为 `Unauthorized`，实际 RSS、卷、Free 额度与 OCI 镜像身份尚无最新 CLI 证明。10 月 23 日 Edge 项目页可见当前 deployment `e42eb7f9-bf7f-4863-be1b-a425df6e7832`、`restore c0001f84709ae134f3b5221574f3965f2f3f55c9`、单副本与卷，Metrics 页显示资源上限 1 vCPU/0.5 GB RAM，但没有正式负载峰值。[Railway 状态页](https://status.railway.com/) 10 月 23 日 22:03 UTC 的公告说明故障涉及社区支持站点 `station.railway.com` 与新注册，现有 dashboard、API、builds、deployments 不受影响；不能将项目页横幅当作本服务宕机证据。

## 2026-10-24 公开历史的卷增长测量

在第四版不变的 `MemoryStore.add`、纯词法和 1 用户缓存下，使用固定来源的公开开发集历史分别写入本机临时 SQLite；问题、答案和评分标注均未写入。LongMemEval-S 的 5,000 条消息使 SQLite 增长 **14.04 MB**（输入文本的 2.950 倍）；PersonaMem-v1 的 5,000 条增长 **13.89 MB**（3.277 倍）；BEAM 100K 的 3,791 条增长 **18.87 MB**（2.273 倍）。`content` 可携带上一条上下文，`terms` 又保存词项副本，这解释了部分放大。完整命令、逐数据哈希、检查点和边界见[卷增长报告](railway-volume-growth-2026-10-24.md)；运行器为 `benchmarks/probe_public_volume_growth.py`。

按样本线性外推，500 MB 空卷约容纳 **10.0–18.0 万条同分布消息**；若沿用 10 月 21 日约 65 MB 已用的旧读数，新增约 **8.7–15.7 万条**。这些是本机样本估计，不能换算为官方 Full 完成率。官网[赛事页](https://agentmemoryleaderboard.ai/competition/)写文本赛道有 6,000 余评测实例、数据规模近 300M tokens，**没有说明这些 token 是否都在同一次 Full 写入 Add**。如果全部累计写入，甚至按每 token 仅 1 个 UTF-8 字节和本次最低 2.273 倍扩张率，SQLite 也约为 682 MB，超过 Free 500 MB 卷；这是条件风险，不能当作已发生的 Full 用量。公开 API 无逐实例 Delete，当前应用也没有自动清除路径。

下一步须核对官网实际 Add 工作量与 Railway 当前卷余量，并在 1 vCPU、512 MiB Linux 容器中用公开长消息回放，记录 `DB+WAL+SHM` 峰值、cgroup RSS/OOM、正式并发延迟和重启恢复。在这些数据齐全前，Free 正式容量门禁仍未通过。
