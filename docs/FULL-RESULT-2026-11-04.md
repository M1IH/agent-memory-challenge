# Full 正式结果（2026-11-04 16:05 北京时间）

## 结论

原 Full 任务 **`teval_c979775416a0bf03` 已成功完成**，取得官网正式分数。

| 项目 | 值 |
|---|---|
| 任务 ID | `teval_c979775416a0bf03` |
| 状态 | **`succeeded`** |
| 阶段 | `completed`（add / search / answer / eval 全部 100%） |
| 进度 | **9602 / 9602**（100.0%） |
| **正式分数** | **`0.5179455948731155`** |
| 完成时间 | `2026-11-04T08:03:43+00:00`（北京时间 16:03:43） |
| 版本 | `v1.5.2-compress-3d5f422` / `version_cae6ba3f3ca4` |
| 运行标签 | `full1-compress-3d5f422-20261101` |
| 赛道 | `textual`（文本，Full 阶段） |
| 参数 | Add 并发 16 / Search 并发 16 / `top_k=100` |
| 错误 | **无** |
| 历史失败 | 38 次（本次为第 39 次尝试） |

证据文件：`data/full-official-result-teval_c979775416a0bf03-2026-11-04.json`
SHA-256 `c33abcc60842a7677b50b5e1023c7cdcb7ccd04a8e81b7d670a708bedc742e80`（20,512 字节）

## 分数构成

| 能力项 | 分数 | 样本数 |
|---|---|---|
| A | 0.569756 | 2,735 |
| B | 0.441783 | 1,944 |
| C | 0.458160 | 1,474 |
| D | 0.616502 | 1,173 |
| E | 0.441473 | 258 |
| G | 0.496586 | 688 |
| H | 0.577713 | 619 |
| streaming | 0.472900 | 3,993 |

## 真正的失败原因（推翻了 403 假设）

用官网 API（`GET /api/v1/evaluations/{id}`）读到的**上一次（第 38 次）失败记录**是：

```json
{"code": "ADD_SERVICE_UNAVAILABLE",
 "message": "HTTPStatusError: 503 Service Unavailable for POST [endpoint] {\"detail\":\"Memory recovery in progress\"}",
 "retryable": true, "stage": "add", "http_status": 503}
```

**不是 403。** 38 次失败的分布：

| 错误码 | 次数 |
|---|---|
| `SEARCH_SERVICE_UNAVAILABLE` | 28 |
| `ADD_SERVICE_UNAVAILABLE` | 4 |
| `EVAL_ACCESS_DENIED` | 2 |
| `EVAL_RUNTIME_ERROR` | 1 |

关键机制：`{"detail":"Memory recovery in progress"}` 是我们 `app/main.py` 里
`require_recovery_ready()` 的固定文案，即冷启动恢复期返回的 503。
这说明此前 34+ 次失败的主体原因是**我方冷启动**，不是平台 403。

> 注：交接文档里"官网把 EVAL_ 归为评分阶段、要求平台维护方检查"的说法，
> 源自官网前端 `app.js` 本地拼装的提示模板（`evaluationErrorCode()` 正则解析
> 错误文本中的 `403` 后生成 `ACCESS_DENIED` 后缀），并非平台权威分类。
> `EVAL_ACCESS_DENIED` 实际只出现过 2 次，不是反复失败的主因。

## 根因链

1. Railway **Free 套餐强制** `sleepApplication=true`
   （实测 `serviceInstanceUpdate` 返回 `BAD_USER_INPUT:
   "Free plan services must have sleepApplication set to true"`）。
2. 空闲 **5.3 / 11.1 / 7.4 分钟**即 `Stopping Container`。
3. 冷启动实测 **19.0 分钟**：
   - 容器启动 → uvicorn 就绪：**3.8 / 4.7 / 4.0 分钟**
   - uvicorn 就绪 → `{"status":"ok"}`：约 **11 分钟**（Bucket 16,978 对象重放）
4. 官方 Add 最多重试 **32 次**，退避上限约 20 秒（实测中位数 19.7 秒）
   → **重试预算约 10 分钟**。
5. **10 分钟 < 19 分钟** → 只要碰上冷启动，必然耗尽重试并失败。

## 修复（免费、未改检索）

唯一有效修复：**持续保活，使容器永不进入空闲休眠**。

- `scripts/keepalive.py`：每 45 秒 `GET /health`，**校验 body `status=="ok"`**
  （不能只看 HTTP 200——恢复期是 `200 + recovering`）。
- Windows 计划任务 `AML-Full-Keepalive`（每 5 分钟自检拉起），
  防止 shell 崩溃导致保活进程被回收（本次已遇到一次）。
- `.github/workflows/keepalive.yml`（提交 `06fe0d0`，已推 `main`）作为云端备份。
- 已禁用本机睡眠：`powercfg` 待机 AC = `0x00000000`。

**验证效果**：修复前容器每 11–16 分钟停机一次；修复后
自 `05:58:05Z` 起连续在线 **>2 小时**无停机，期间评测从 99.9% 顺利跑完。
修复后**再无任何 503**（41 次 503 全部发生在 `05:39:27Z` 之前）。

## 对"不要降低检索成绩"的交代

- 检索算法、排序、分词、返回构造**完全未改**。
- 部署 `ed67f042-12b5-4700-be89-261568cfef84` 自始至终未变，未重新部署。
- 取得分数的版本就是原候选 `v1.5.2-compress-3d5f422`。
- 分数 `0.51795` 高于历史 Smoke 63.81/68.09 所对应的不同版本语境，
  且**无需回退**，也未使用 68.09 保底版本。

## 仍未完成的

- 公开榜单页（`/leaderboard/academic/textual`）当前**尚未出现**本条目
  （页面未含 `Nagasaki` / `0.5179` / `c979775416a0bf03`）。
  正式分数已在 API 侧可核验，榜单展示可能需平台刷新或人工发布。
- 服务将继续保活至截止后（约 96 小时窗口），以满足"维持 API 可用"要求。
