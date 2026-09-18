# 第二期自托管部署清单

核对日期：2026-09-18。本文选择 Railway 作为低成本候选，但不把它写成唯一选择。
正式创建资源前必须重新核对价格，并由参赛者确认账号、付款和对外发布。

## 目标与硬门槛

- 对公网提供 HTTPS `GET /health`、`POST /add` 和 `POST /search`。
- Endpoint 提交后至少稳定运行 30 天；不能使用会长期休眠或试用期早于 30 天结束的配置。
- 固定一个公开 Git Commit 和与其对应的镜像 ID/digest，不在 Full 期间自动漂移。
- SQLite 数据、日志和备份只用于赛事；任务结束后 30 天内删除评测数据及备份。
- 服务只运行一个副本。SQLite 不能由多个副本共享写入同一个卷。

## Railway Dashboard 部署

1. 在 Railway 新建项目，选择 **Deploy from GitHub repo**，连接公开仓库
   `M1IH/agent-memory-challenge`，选择最终固定 Commit 所在分支。仓库根目录的
   `Dockerfile` 会负责构建，不要另填会绕开 Dockerfile 的启动命令。
2. 给服务创建一个 Volume，挂载路径填写 `/data`。数据库路径必须位于该卷上。
3. 在 Variables 中设置下面的值。密钥只放 Railway Secret，不写进 Git、截图或报名材料：

   ```text
   AML_API_KEY=<至少32字节的随机密钥>
   AML_LOCKDOWN=true
   AML_DB_PATH=/data/memory.db
   AML_EMBED_ENABLED=true
   AML_MEMORY_CACHE_USERS=1
   PORT=8000
   RAILWAY_RUN_UID=0
   ```

   Railway 的 Volume 默认以 root 用户挂载，而当前镜像默认使用 UID/GID 10001。
   `RAILWAY_RUN_UID=0` 是让该平台上的 `/data` 可写所必需的兼容设置；它降低了容器内
   权限隔离，因此只用于 Railway。其他能正确设置卷属主的平台继续保持非 root 运行。
4. 初始只设一个副本，内存至少 512 MiB，建议 1 GiB 起步；CPU 和内存都应以部署后的
   真实 Smoke/负载结果为准。512 MiB 只是 CI 中有界 Smoke 通过的下限证据，不是正式
   Full 容量承诺。
5. 在服务 Settings 中把 Healthcheck Path 设置为 `/health`，超时建议至少 300 秒。
   镜像首次启动需要加载本地模型。Railway 健康检查只负责发布切换，不提供持续监控。
6. 在 **Networking -> Public Networking** 选择 **Generate Domain**。Railway 会提供
   `.railway.app` 域名和自动 TLS 证书。只向官方提交 `https://` 地址。
7. 关闭不受控的 GitHub 自动部署，或只让固定发布分支触发。正式 Full 前记录部署详情页、
   Commit SHA、镜像 ID/digest和配置时间，但任何截图都不能包含 API Key。

## 首次上线验证

先在本机 PowerShell 临时设置环境变量；关闭终端后变量消失：

```powershell
$env:AML_BASE_URL = "https://<railway-domain>"
$env:AML_API_KEY = "<deployment-secret>"
python scripts\smoke_remote.py
```

只有看到 `REMOTE SMOKE PASS` 才能继续。该 Smoke 会真实写入一条带随机标记的合成
记忆，并验证 HTTPS、鉴权、Add 回显、幂等重放、立即 Search 和基础用户隔离。
它不是官方 Smoke，也不能证明 Full 容量。

随后在 Railway 触发一次重启，再用同一个 Endpoint 重新运行 Smoke。另需检查：

- `/health` 返回 2xx；无鉴权 Search 返回 401。
- Railway 日志没有 API Key、请求正文、数据库路径外泄或持续重启。
- Volume 使用量、内存峰值和 CPU 没有逼近套餐上限。
- 更新或回滚时，挂卷服务可能短暂停机；不要在官方 Full 运行中发布。

## 运行 30 天的保障

- 使用 Railway 外部的 HTTPS 监控每 5 分钟检查 `/health`；Railway 自带部署健康检查
  不会持续探测。告警只记录状态码和延迟，不记录 API Key 或请求正文。
- 每天查看一次失败率、重启次数、内存、CPU 和卷容量。磁盘接近上限时先备份再扩容。
- 在 Full 前做一次可恢复备份，并记录备份时间。不要把数据库提交到仓库或上传公共网盘。
- `/health` 只能证明数据库当前可读；真正的可写性和检索可见性仍由远程 Smoke 验证。
- 如果部署失败，先回滚到已通过远程 Smoke 的同一 Commit/镜像，不要在生产数据库上
  临时改表或运行未经测试的代码。

## 报名时需要填写或保存的内容

- 公开 GitHub 仓库 URL、固定 40 位 Commit SHA、许可证。
- HTTPS Add Endpoint、Search Endpoint、Health Endpoint。
- 鉴权格式（推荐 `Authorization: Bearer <key>`）及安全传递给官方的 Key。
- 容量声明：单副本、内存/CPU/卷额度，以及经过实际验证的并发和语料边界。
- 方法说明、相对既有工作的变化、第三方模型及依赖署名。
- 远程 Smoke 时间、发布清单、镜像 ID/digest和回滚版本。

## 正式外部动作边界

创建 Railway 付费资源、购买套餐、公开 Endpoint、提交报名、启动官方 Smoke 或 Full
之前，必须由参赛者确认。每个 Key/赛道最多两次 Full，且第二次有 30 天解锁等待，
不能把第一次 Full 当作普通调试运行。

## 资料来源

- [赛事 Add/Search API 指南](https://agentmemoryleaderboard.ai/api-guide)
- [Railway Volumes](https://docs.railway.com/volumes)
- [Railway Public Networking](https://docs.railway.com/networking/public-networking)
- [Railway Healthchecks](https://docs.railway.com/deployments/healthchecks)
