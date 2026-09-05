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
  -e AML_API_KEY=replace-with-a-long-random-secret `
  -v agent-memory-data:/data `
  agent-memory-challenge:local
```

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

运行 `python -m benchmarks.run_ablation` 可比较纯词法、纯向量、完整融合、
关闭概念扩展、关闭时间加权、等权 RRF，以及不同 `top_k` 的指标差异。

设置 `AML_EMBED_ENABLED=false` 可关闭向量通道，退回纯关键词检索。

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

## 数据合规

评测数据只用于赛事评测，不用于训练、分析或传播。部署方应在一次评测结束
后的 30 天内删除数据库及其备份，并避免在访问日志中记录请求正文。
