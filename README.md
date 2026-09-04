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
