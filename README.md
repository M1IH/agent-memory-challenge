# AML Memory Entry

个人参赛的 Agent Memory Challenge 文本赛道开源基线系统。

本项目采用 [MIT License](LICENSE)。

当前版本实现官方同步 `Add / Search` 协议，使用 SQLite 持久化，并通过
`user_id` 严格隔离不同用户。检索融合 BM25 风格词项匹配、本地 BGE
英文向量、选择题选项通道和时间更新加权。模型在 Docker 构建时固化，
运行时不调用付费 API，也不需要联网。

## 本地运行

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：`GET /health`

## Docker 运行

镜像会在构建时下载并固化本地嵌入模型，容器启动和检索阶段不需要联网：

```powershell
docker build -t agent-memory-challenge:local .
docker run --rm -p 8000:8000 `
  --memory 1g --memory-swap 1g `
  -e AML_API_KEY=replace-with-a-long-random-secret `
  -v agent-memory-data:/data `
  agent-memory-challenge:local
```

CI 会在 `512m` 内跑有界 Smoke；嵌入批大小降为 64 后，已观测到稳态约
`328 MiB`、峰值约 `335 MiB`。本地示例仍保留 `1g` 上限；这不是公式容量承诺，
更大语料、更多用户或更高并发必须
重新压测。如果启用 `AML_MEMORY_CACHE_USERS`，必须保留明确的容器内存上限。

验证服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

生产或公开评测环境必须设置 `AML_API_KEY`，并通过
`Authorization: Bearer <key>`、`Authorization: Token <key>` 或
`X-Api-Key: <key>` 发送。命名卷 `agent-memory-data` 用于在容器重启后保留
SQLite 数据。

## Add

`POST /add`

```json
{
  "request_id": "eval:run:sample:chunk-0",
  "messages": [
    {"role": "user", "timestamp": 1704067200000, "content": "我喜欢喝乌龙茶。"}
  ],
  "user_id": "eval:run:user-0",
  "session_id": "eval:run:session-0"
}
```

系统只会在消息已写入且可检索后返回成功，并原样回传三个标识字段。
同一用户重复提交完全相同的 `request_id` 和正文会安全返回成功；如果复用
`request_id` 却改变正文，服务返回 HTTP 409，避免一次重试写出互相矛盾的记忆。
旧数据库若已有记忆但没有请求校验记录，重用旧请求 ID 也会返回 409；无法从
带上下文的展示文本可靠还原原始请求，服务不会猜测等价性或静默追加。
空白正文和无法表示的时间戳会返回 HTTP 422；消息角色保持开放兼容，并限制为
非空且最长 32 个字符。
单次 Add 的正文总量默认最多 200,000 字符，可用正整数
`AML_MAX_ADD_CHARS` 调整；超限会在分词、嵌入和写库前返回 HTTP 413。
运行期 SQLite 故障统一返回不含内部路径或请求正文的 HTTP 503 JSON；服务端日志
只记录异常类型。`/health` 会执行轻量级存储读取，数据库不可用时同样返回 503。
损坏数据库会拒绝启动，不会静默创建空库覆盖原文件。

## Search

`POST /search`

```json
{
  "query": "我喜欢喝什么？",
  "options": ["A. 咖啡", "B. 乌龙茶"],
  "user_id": "eval:run:user-0",
  "top_k": 100
}
```

响应中的 `data` 按相关性从高到低排列。没有相关记忆时返回空数组。
Search 的 query 与 options 总量默认最多 200,000 字符，可用正整数
`AML_MAX_SEARCH_CHARS` 调整；超限返回 HTTP 413。赛事官方正常请求远低于该默认值。

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 本地检索评测

```powershell
python -m benchmarks.run_benchmark
```

脚本输出 Hit@1、MRR 和各题型得分，用于确保检索增强不是只凭感觉调参。
使用 `--suite extended` 会在 15 个核心案例之外运行 110 个确定性合成案例；
`--json-output result.json` 可保存机器可读指标，`--fail-on-miss` 可让任何
Evidence Hit@5 漏召回直接使命令失败。扩展案例只用于回归测试，不含官方评测数据。

`--suite hard` 单独运行 6 个高干扰诊断场景（每题 12 条干扰记录），包含
多跳、列表、中文关联和无关更新。该套件按真实返回记录对应的来源 ID 评分，
不按答案文本匹配；来源标签不会进入索引正文。输出 `complete_at_k` 表示在
指定 `top_k` 内找齐全部所需证据的题目比例。JSON 同时保存逐题排名、返回内容、
套件摘要、检索代码摘要、配置和运行时版本，便于复核。旧 core/extended 仍用
文本匹配，不能和 hard 的分数直接比较。`--fail-on-miss` 仍以 Hit@5 为门槛。
这 6 题是开发诊断集，不是独立盲测或获奖能力证明；hard 暂不设置全通过门槛。

负载测试的混合阶段会按请求比例交错提交 Add 和 Search，避免线程池队列顺序把
所谓混合测试退化为先 Add 后 Search。JSON 报告区分预载与预计最终记忆数，记录
两类吞吐、延迟、错误和 Top-1 失败样本，便于复现偶发排序波动。

用 `--soak-seconds 600 --soak-add-workers 2 --soak-search-workers 4` 可按时间持续
运行混合负载。soak 报告另外记录每个 worker 的前进量、p50/p95/p99、错误类型、
RSS，以及 SQLite 主文件、WAL 和 SHM 的总占用；持续时间为 0 时保持原有限批次行为。

运行 `python -m benchmarks.run_fts_probe` 可复现直接用 SQLite FTS5 过滤候选的
召回风险。该脚本是只读设计探针，不会切换正式 Search；当前证据表明直接过滤会
漏掉零词面重叠和跨语种证据，因此没有启用这一方案。

运行 `python -m benchmarks.run_ablation` 可比较纯词法、纯向量、完整融合、
关闭概念扩展、关闭时间加权、关闭一跳实体关联、等权 RRF，以及不同 `top_k` 的指标差异。

一跳实体关联只从高相关记录和明确身份/归属句中提取重复出现的拉丁专名，
用于召回同一实体的下一条证据；通用房间类型、星期和问题中已有实体不会扩展。
这是保守的候选扩展，不等同于完整知识图谱或不限深度推理。

默认 RRF 融合权重为词法 `1.5`、向量 `0.5`。该配置在固定 hard 诊断集上
保住了列表证据，在旧扩展回归集上未降低 Hit@1、Hit@5 或 MRR；它仍属于
开发集调优，正式提交前需要独立场景和官方 Smoke/Full 结果验证。

设置 `AML_EMBED_ENABLED=false` 可关闭向量通道，退回纯关键词检索。
默认允许两个并发嵌入任务，在当前 CPU 基线上相较完全串行显著降低 Add
排队时间；可通过正整数 `AML_EMBED_CONCURRENCY` 按部署 CPU 和内存调整。
单次模型推理默认按 64 条分批，可用正整数 `AML_EMBED_BATCH_SIZE` 调整。
较大批次会明显增加峰值内存；修改前应同时对 Add 吞吐和容器峰值做 A/B。
当 Add 与 Search 同时等待嵌入槽位时，查询编码优先，避免长批量 Add 队列
阻塞在线检索；连续放行 8 个查询后会让一个等待中的 Add 先执行，避免持续查询
令写入无限期饥饿。总并发上限不变，第三方编码器未显式声明能力时仍调用普通
`encode` 接口。
对于最多出现在 4 条记忆中的数字型复合标识符（例如项目编号），融合阶段会保留
精确词法匹配，避免对数字不敏感的密集排名反超正确记录；该保护不进入 dense-only
消融，也不会提升普通词或中文片段。
持久化向量会绑定到 `AML_EMBED_MODEL`、float32 编码和归一化版本；存在向量时
若身份不一致，服务拒绝打开旧索引并要求重建，避免同维度的不同模型静默混用。
自定义编码器应提供稳定的 `index_identity` 字符串。
`AML_MAX_CONTEXT_CHARS` 控制相邻消息拼接后的最大字符数，默认 `1200`，必须是
正整数；服务会在启动时拒绝非法配置，而不是等到 Add 请求时才失败。
`AML_MEMORY_CACHE_USERS` 可缓存最近使用的用户语料快照，`0` 表示关闭且为默认值。
启用后必须填写非负整数；缓存使用数据库内用户版本号跨连接失效，同一用户的并发
冷加载会合并为一次，LRU 上限按用户数控制。`AML_MEMORY_CACHE_MAX_BYTES`
设置缓存快照的估算字节预算，默认 `67108864`（64 MiB）且必须为正整数；单个
超预算用户仍会正常检索，但不会留在缓存中。该值是 Python 对象与向量缓冲区的
保守估算，不等于操作系统 RSS 硬上限。缓存会用常驻内存换取重复 Search 延迟，
应根据部署内存测量后配置，不能只根据本机速度盲目启用。
负载基准报告的 `memory` 字段会记录存储初始化、Add 后和 Search 后的
当前进程 RSS；这是整个 Python 进程的常驻内存，不是缓存对象的精确字节数。
检索还包含有频率上限的专名关联：英文保持一跳，中文对保守识别的人名和快递名
最多再传播一跳；可用 `--disable-linkage` 在本地基准中关闭并做消融比较。
对明确询问“已经打包/已经确认”的列表查询，排序会区分完成事实、明确否定和
他人行为；查询本身为否定问法时不会套用这条正向规则。
小型中英概念表为预订、住宿等常见表达提供可审计的跨语言词法桥；英文概念
使用单词边界匹配，避免短词在更长单词中误触发。

## 端到端 Smoke

```powershell
python scripts\smoke_local.py
```

该脚本会临时启动真实 Uvicorn 服务，验证健康检查、三种鉴权方式、同步写入和
立即检索，结束后自动关闭服务并删除临时数据库。

GitHub Actions 还会构建完整 Docker 镜像，并在容器无网络的情况下执行 Add/Search
冒烟测试，以确认嵌入模型确实已固化进镜像。

## 本地负载测试

```powershell
python -m benchmarks.run_load_test
```

该测试启用真实向量模型，模拟每数据集 48 个 Add、每次 20 条消息，以及
32 个 Search 工作者，用于发现 CPU 延迟和并发瓶颈。
参数可用于复现更大规模的纯存储/词法基线，例如：

```powershell
python -m benchmarks.run_load_test --add-requests 500 `
  --messages-per-request 20 --search-requests 96 `
  --add-workers 64 --search-workers 32 --top-k 100 `
  --no-embeddings --json-output benchmarks/load-10k-lexical.json
```

JSON 报告包含成功写入吞吐、错误类型、Search p50/p95/p99、吞吐和 Top-1
准确率。`--no-embeddings` 只用于隔离 SQLite、词法评分和并发开销，不代表
正式提交配置。

容量阶梯可加入 `--max-rss-bytes 1073741824`，记录当前与进程生命周期峰值 RSS，
并在峰值无法读取或超过 1 GiB 时让命令失败。它是测得峰值的回归门禁，不是操作系统
硬内存隔离；硬限制仍需使用 Docker `--memory` 并检查 cgroup/OOM 状态。
`--users 8` 可把请求稳定分散到多个用户；报告会记录各用户的记忆数和 generation，
并主动检索相邻用户的精确标识符，任何跨用户泄漏都会让命令失败。

## 数据合规

评测数据只用于赛事评测，不用于训练、分析或传播。部署方应在一次评测结束
后的 30 天内删除数据库及其备份，并避免在访问日志中记录请求正文。
