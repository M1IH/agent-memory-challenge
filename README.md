# AML Memory Entry

个人参赛的 Agent Memory Challenge 文本赛道开源基线系统。

本项目采用 [MIT License](LICENSE)。

第二期要求参赛者自托管公网 HTTPS Add/Search API。部署前请完整执行
[第二期自托管部署清单](docs/cycle-2-deployment.md)，不要只提交仓库等待平台代部署。

当前版本实现官方同步 `Add / Search` 协议，使用 SQLite 持久化，并通过
`user_id` 严格隔离不同用户。检索融合 BM25 风格词项匹配、本地 BGE
英文向量、选择题选项通道和时间更新加权。模型在 Docker 构建时固化，
运行时不调用付费 API，也不需要联网。

## 阶段检查点（恢复工作时先读）

> 最后核对：2026-09-22（Asia/Shanghai）。本节是上下文压缩、新任务和交接后的
> 恢复入口。继续工作前先核对这里，再从“下一步优先级”中最高的未完成项开始；
> 每次完成重大外部动作后同步更新本节。历史细节见
> [迭代检查点](docs/iteration-checkpoint.md)、
> [官方评测笔记](docs/official-evaluation-notes.md)和
> [Full 前提分审计](docs/score-improvement-audit.md)、
> [第二期部署清单](docs/cycle-2-deployment.md)。

### 最终目标与当前阶段

- 目标：以获奖为导向，在零预算优先的前提下安全完成 Agent Memory Leaderboard
  文本赛道的官方评测；正确性、服务稳定性和提交可靠性优先于展示包装。
- 当前阶段：代码、公开仓库和公网部署已就绪，报名已审核通过；第一次正式文本
  Smoke 已于 2026-09-22 12:16:07（UTC+8）通过，文本分支 18/18、streaming
  分支 28/28，Full 准入已经解锁。下一步是完成 **Full 前门禁**，向用户报告收益、
  风险和剩余次数，并取得新的明确确认；当前不得直接启动 Full。
- 粗略总体进度：约 `99.6%`。这是项目管理估计，不是官方成绩；剩余工作虽少，
  但 Smoke 和首次 Full 都是高影响门禁，不能按普通调试操作处理。

### 已确认的发布基线

| 项目 | 当前基线 |
| --- | --- |
| 公开仓库 | `M1IH/agent-memory-challenge` |
| 固定 Git Commit | `50da01c53e45ca91a4a9fad7487aa51462d7b10a` |
| GitHub Actions | run `35433333355`，上述精确 SHA 的 `tests` 已成功 |
| 公网服务 | `https://api-production-40d75.up.railway.app` |
| 健康检查 | 2026-09-22 核对为 HTTP 200、`{"status":"ok"}` |
| Railway 部署 | deployment `6027923e-33e2-45d1-b846-016294a72980`，状态 `SUCCESS` |
| 持久卷 | `/data`，最近核对约 33 MB / 500 MB |
| 线上检索模式 | `AML_EMBED_ENABLED=false`，纯词法/BM25；不要把本地真实 BGE 结果写成线上能力 |
| 官方系统 | `Nagasaki soyo's memory` |
| 官方版本 | `v1.0.0-lexical-50da01c`，version id `version_a7dc552e7b79` |
| 榜单 | 学术榜，文本赛道 |

本地单元测试最近记录为 152 项通过；这不是“没有任何 Bug”的证明。容量与检索指标
均是指定配置下的测量边界，不得外推为官方 Full 成绩或无限容量承诺。

### 官方评测状态（不得混淆）

- 报名已审核通过，Add/Search Endpoint 和鉴权绑定已由官网验证有效。
- 2026-09-21 启动过一次独立兼容性测试，test id 为
  `itest_e80ae00a7cfa46e5bd9e`。Railway 日志显示成批 Add/Search 请求除预期的
  未鉴权探针外均返回 HTTP 200；但临时查询令牌丢失，不能仅凭日志宣称测试通过。
- 2026-09-22 11:51（UTC+8）按官网 `textual-v1` 合同启动第一次正式文本 Smoke：
  evaluation id `teval_4bbe55d760a5fdd8`，参数为 Add 并发 16、Search 并发 16、
  `top_k=100`。文本主分支完成 18/18；streaming 分支在 26/28 时失败，官方终态为
  `failed`，错误 `EVAL_TIMEOUT: ReadTimeout: POST [endpoint]`，并标记
  `retryable=true`。我方 `/health` 保持 HTTP 200，期间可见 Add/Search 日志均为
  HTTP 200，未出现服务异常；这些证据倾向于官方流式评测链路或其下游超时，但不足以
  断言完全与我方无关。
- 本次正式 Smoke 已计入 `smoke_used=1/30`，文本 Smoke 仍为 `not_passed`；下一次
  开放时间为 2026-09-22 12:51:11（UTC+8）。`full_used=0/2`，Full 仍不可启动。
- 12:05 对上述同一 evaluation id 执行一次官方“从断点续跑”，平台确认复用了文本
  主分支的 `succeeded 18/18` 检查点；streaming 分支再次停在 26/28，并于 12:10:34
  以完全相同的 `EVAL_TIMEOUT: ReadTimeout: POST [endpoint]` 失败。续跑没有创建新任务，
  `smoke_used` 仍为 1，正式评测列表仍只有这一项。
- 12:16:07 再次只读核对时，原 evaluation id 已由官网更新为 `succeeded`；没有发起
  新续跑或第二次 Smoke。最终进度为 46/46，其中文本 18/18、streaming 28/28；
  官方结果分数为 `0.5175347222222222`。版本资格明确显示 `smoke=passed`、
  `full_allowed=true`、`smoke_used=1/30`、`full_used=0/2`。
- 同期项目内归因复查为 152 项本地测试通过、源码编译通过、仓库秘密扫描无命中；
  公网 `/health` 为 HTTP 200，Railway 服务和固定部署正常，最近评测相关 Add/Search
  请求除预期未鉴权探针外均为 HTTP 200，GitHub `main` 最新 CI 成功。这些证据未发现
  项目侧导致 streaming 超时的问题，因此没有为平台侧故障猜测性修改业务代码。
- 用户已经授权运行官方文本 Smoke；**尚未授权首次 Full**。Smoke 通过后必须先完成
  下方 Full 前门禁，再向用户展示证据并取得明确确认。

### 下一步优先级（严格按顺序）

1. **P0：执行 Full 前提分审计。** 按 [提分审计](docs/score-improvement-audit.md)
   先冻结新的独立高干扰套件，再验证有界关系链、时间/否定和结果覆盖重排；只有新盲测
   与既有回归同时提升，才允许创建新版本并消耗一次 Smoke。不得在旧版本名下静默改部署。
2. **P0：Smoke 通过后的 Full 前门禁。** 再核对公网 `/health`、Add/Search 鉴权与
   即写即搜、持久卷恢复、Railway 额度/试用期、固定线上 SHA、GitHub CI、日志无秘密、
   无自动部署漂移，并评估纯词法线上配置是否能承受官方负载。
3. **P0：首次 Full 决策。** 把门禁结果、剩余 `0/2` 或实际次数和风险报告给用户；
   只有得到新的明确确认后才能启动 Full。Full 运行期间禁止部署、改变量或重启服务。
4. **P1：Full 后响应。** 持续监控健康与部署，但不查看、训练或传播官方评测数据；
   保存官方允许公开的结果。如果失败，保留证据，先分析再决定是否使用第二次机会。
5. **P2：收尾。** 根据官方要求清理评测数据及备份、更新公开文档和最终发布标签；
   不公开任何 Key、Token、私有请求正文或保留评测材料。

### 操作边界与秘密处理

- 不把 LDBD Key、Add/Search Token、`AML_API_KEY` 写进 README、Git、命令行参数、
  截图、日志或聊天回复；优先从剪贴板或进程环境读取，并且永不回显。
- 已在聊天中出现过的秘密不应再次复制；如怀疑泄漏，联系官方/平台轮换，而不是
  把旧值提交到仓库。仓库中的示例只能使用明显占位符。
- 不自动付款、升级 Railway、注册新账户、改变公开范围或启动 Full。
- 不在官方 Smoke/Full 运行中修改 Railway 配置、代码、镜像、卷或自动部署策略。
- 不把本地合成测试、Docker Smoke、兼容性测试或 HTTP 200 等同于官方评测通过。
- 如果浏览器控制桥连接失败，优先使用官网只读 API 核对状态；涉及正式提交时不得
  盲点。可在新 Codex 任务中用 `@Browser` 打开 Bing 并读取标题，区分任务会话故障
  与浏览器整体故障。

### 每轮迭代的完成标准

任何代码变更都应先复现问题并增加回归覆盖，然后运行相关测试和完整测试，复查整体
代码与秘密泄漏风险，提交并推送，最后等待**精确提交 SHA** 的 GitHub Actions 成功。
文档或外部状态更新必须注明核对日期；易变化的官网状态、Railway 额度和评测次数不得
只凭本节旧记录作决定。

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
docker build --build-arg "VCS_REF=$(git rev-parse HEAD)" -t agent-memory-challenge:local .
docker run --rm -p 8000:8000 `
  --memory 1g --memory-swap 1g `
  -e AML_API_KEY=replace-with-a-long-random-secret `
  -v agent-memory-data:/data `
  agent-memory-challenge:local
```

镜像内服务以固定的非 root 用户 `10001:10001` 运行；命名卷首次创建时会继承
`/data` 的写权限。若改用宿主机 bind mount，部署前必须把挂载目录授权给该 UID/GID，
否则服务会安全地因数据库不可写而拒绝启动。

Docker 和 Linux CI 使用 `requirements.lock` 中的完整传递依赖版本；基础 Python
镜像也固定到内容摘要。因此同一提交不会因上游标签或间接依赖漂移而悄悄改变。
`requirements.txt` 保留直接依赖，便于 Windows 本地开发；升级依赖时必须同步更新
锁文件，并重新通过完整 Docker 离线 Smoke。

构建参数会把当前 Git SHA 写入 OCI `org.opencontainers.image.revision` 标签。提交前用
`docker image inspect -f '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}' agent-memory-challenge:local`
同时记录不可变镜像 ID 与代码版本；CI 会拒绝 revision 与当前提交不一致的镜像。
`python scripts/release_manifest.py` 会在工作区不干净、关键发布文件缺失，或镜像
ID/revision 不匹配时失败；CI 会输出包含关键文件哈希的 JSON 发布清单。
清单还会以 `release-manifest-<Git SHA>` 名称作为 Actions artifact 保存 30 天；
artifact 缺失会直接让 Docker job 失败。

CI 会在 `512m` 内跑有界 Smoke；嵌入批大小降为 64 后，已观测到稳态约
`328 MiB`、峰值约 `335 MiB`。本地示例仍保留 `1g` 上限；这不是公式容量承诺，
更大语料、更多用户或更高并发必须
重新压测。如果启用 `AML_MEMORY_CACHE_USERS`，必须保留明确的容器内存上限。

验证服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Docker 镜像默认设置 `AML_LOCKDOWN=true`，因此缺少 `AML_API_KEY` 或兼容的
`API_KEY` 时会在启动阶段失败，而不会意外暴露无鉴权的 Add/Search。仅在明确隔离的
本地开发环境中，才可显式设置 `AML_LOCKDOWN=false`。生产或公开评测环境通过
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
空白正文、纯空白的请求/用户/会话标识、纯空白角色和无法表示的时间戳会返回
HTTP 422；消息角色保持开放兼容，并限制为非空白且最长 32 个字符。
单次 Add 的正文总量默认最多 200,000 字符，可用正整数
`AML_MAX_ADD_CHARS` 调整；超限会在分词、嵌入和写库前返回 HTTP 413。
原始 JSON 请求体还受 `AML_MAX_REQUEST_BYTES`（默认 2,000,000 字节）限制，
该检查在鉴权依赖和 JSON 解析前执行，可避免超大请求先占满进程内存。
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
纯空白 query、user_id 或 option 会在检索前返回 HTTP 422。

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
Evidence Hit@5 漏召回直接使命令失败。报告还绑定套件、实际 embedding identity、
关键运行参数，以及检索与评分源码的逐文件/组合 SHA-256。扩展案例只用于回归测试，
不含官方评测数据。

`--suite blind2` 运行第二套冻结高干扰盲测。其案例和首次真实 BGE 结果在任何
针对性调优前固定；若要开发修复，必须复制为开发集，不能直接改写盲测案例。
`--suite blind3` 运行第三套冻结高干扰盲测；该套件必须先以固定哈希提交并通过
CI，之后才能首次执行和保存基线。首次执行后同样禁止原地修改案例。

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
容量门禁还可用 `--max-rss-bytes`、`--max-add-p95-seconds` 和
`--max-search-p95-seconds` 设置峰值内存及基础 Add/Search p95 上限；超过任一上限时
报告仍会写出，但命令以失败退出。阈值必须来自明确部署目标，不应事后迁就结果。
基础、mixed 与 soak 阶段都保存各自的 p95 门禁结果，避免持续阶段绕过延迟上限。

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
持久化向量会绑定到 `AML_EMBED_MODEL`、模型 revision、模型与 tokenizer SHA256、
float32 编码和归一化版本；存在向量时若身份不一致，服务拒绝打开旧索引并要求重建，
避免同维度的不同模型静默混用。Docker 构建还会核对固化文件的 revision 和哈希，
上游同名模型漂移时直接构建失败。覆盖 `AML_EMBED_MODEL` 时也必须同时提供该模型的
`AML_EMBED_MODEL_REVISION`、`AML_EMBED_MODEL_SHA256` 和
`AML_EMBED_TOKENIZER_SHA256`。自定义编码器应提供稳定的 `index_identity` 字符串。
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

该脚本会临时启动真实 Uvicorn 服务，验证健康检查、三种鉴权方式、同步写入、
同请求幂等重放、立即检索和用户隔离，结束后自动关闭服务并删除临时数据库。

GitHub Actions 还会构建完整 Docker 镜像，并在容器无网络的情况下执行 Add/Search
冒烟测试，以确认嵌入模型确实已固化进镜像。

公网或临时 HTTPS 部署完成后，用环境变量传入地址和密钥，避免密钥出现在命令行
历史或进程参数中：

```powershell
$env:AML_BASE_URL = "https://memory.example.com"
$env:AML_API_KEY = "replace-with-the-deployment-secret"
python scripts\smoke_remote.py
```

远程 Smoke 默认拒绝明文 HTTP、URL 内嵌凭据、query 和 fragment，并验证健康检查、
未鉴权 Search 必须返回 401、Add 精确回显与幂等重放、三种鉴权方式、新写入证据
立即 Top-1 可检索，以及随机外部用户无法检索该证据。它会写入一条带随机标记的
合成记忆，因此只应对明确用于评测的部署运行；
评测结束时应随数据库一起删除。隔离的本机演练可显式添加 `--allow-http`。

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
启用内存缓存时，`memory.cache` 还会记录命中、等待者复用、数据库加载、LRU 淘汰、
Add 失效、超预算拒绝、最终常驻用户/估算字节和未完成加载数；这些计数用于证明
负载中确实发生缓存换入换出，不是精确内存分析或跨进程指标。

## 数据合规

评测数据只用于赛事评测，不用于训练、分析或传播。部署方应在一次评测结束
后的 30 天内删除数据库及其备份，并避免在访问日志中记录请求正文。
