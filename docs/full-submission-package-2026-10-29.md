# 首次 Full 提交材料包（2026-10-29，压缩候选已上线）

## 已核实的可填信息

| 字段 | 目前准确值或说明 |
| --- | --- |
| 系统 | `Nagasaki soyo's memory`；文本赛道、学术榜，沿用已经通过五次 Smoke 的既有 Key |
| 已通过 Smoke 的版本 | `v1.4.0-stage-notice-5d1f82d`，任务 `teval_ba5f1ec7c158cd00`，2026-10-27 成功，平均 68.09 |
| 公开仓库 | `https://github.com/M1IH/agent-memory-challenge`；必须同时给精确提交，不能只填仓库根地址 |
| 已通过 Smoke 的精确源码 | `https://github.com/M1IH/agent-memory-challenge/commit/5d1f82d3d7789051b47c4a9f70f1dbf07d07c794` |
| 当前生产部署 | Railway `production/api`，压缩候选 deployment `fac32883-bdb3-40b5-a273-3089e661c38a`，镜像 `sha256:d81cf84e593aa1546a1980c96973cb2643215e5a8ece42d14dabd83c7ab15463`；2026-10-29 CLI 显示 SUCCESS。第五版部署 `daa06888-0fc1-480c-8184-6e80530eea48` 是已通过 Smoke 的回退锚点 |
| HTTPS 接口 | `https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`、`https://api-production-40d75.up.railway.app/health` |
| 鉴权 | `Authorization: Bearer <Memory System Key>`；Key 只能填官网指定安全字段，不写进公开材料 |
| 当前运行配置 | 纯词法、`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`、`AML_COMPRESS_TEXT=true`；新写入的 SQLite 文本和词项以 zlib 压缩保存，旧行仍可读 |
| 当前候选精确源码 | `https://github.com/M1IH/agent-memory-challenge/commit/3d5f42258365a57a1425ae64f01525a06429f26c`；尚无对应官方 Smoke 分数 |
| 当前资源 | Railway Free，单副本，1 vCPU/0.5 GB RAM 上限，`/data` 卷 66.363392/500 MB（2026-10-29 CLI）；当前账期用量约 `$0.00585`，月末 11 月 20 日；本次 `/health` 冷唤醒 200，9.56 秒 |

## 可粘贴的方法与来源说明

> 系统提供自托管的同步 Add/Search HTTPS API。Add 按 `user_id` 和 `session_id` 将原始对话及时间信息保存在 SQLite；Search 限定同一用户，结合 BM25 风格词项匹配、有限的实体关联、选择题选项、显式时间和当前状态信号，返回带来源的证据供平台统一回答器使用。当前生产关闭 embedding，参赛服务不调用回答 LLM。第五版增加对用户明确通知环境变化后证据的阶段优先排序；历史查询与没有该类通知的历史保持原排序。第五次文本 Smoke 取得 68.09。代码与依赖见上述精确提交。此为本项目实现；方法设计参考 AML Add/Search 协议及仓库 `docs/external-memory-systems-review.md` 中列出的 Graphiti、Mem0、HippoRAG、LangMem 等公开系统，不声称集成其源码。本项目代码以 MIT 许可公开；镜像含固定 BGE ONNX 文件但当前运行关闭该能力，第三方模型许可与来源应按仓库说明分别列示。

上段方法说明中的 68.09 和阶段优先排序属于第五版实测。压缩候选沿用检索排序，但尚无对应官方 Smoke；在官网应作为独立版本填写精确源码 `3d5f42258365a57a1425ae64f01525a06429f26c` 和当前镜像 digest，不能沿用第五版版本名或分数。

## Full 前仍需取得的证据

1. **容量：**500 MB 卷能否承受本次 Full 的累计 Add、WAL 峰值和评测持续时间。当前没有官方单次 Full 的精确写入字节数；公开 100k 历史压缩后增量 161.26 MB 只是本地情景，不能据此确认整场可运行。Linux 1 vCPU/512 MiB、10k 长消息、16/16 并发测试已通过（[run 40818226083](https://github.com/M1IH/agent-memory-challenge/actions/runs/40818226083)）：Add/Search 零错误、96/96 Top-1、Search p95 12.60 秒、cgroup peak 105,177,088 B、OOM 0。线上 Add/Search 与同镜像重新部署后的持久化检索均通过。仍需官方 Smoke 实际卷增长和持续稳定性证据。
2. **版本：**压缩候选已部署，需在官网新增独立版本并运行该版本的 Smoke；提交 `3d5f42258365a57a1425ae64f01525a06429f26c` 的 CI 已通过，390/390 公开检索题的逐题来源排序和指标与未压缩版完全一致。仍需核实官网版本绑定和官方结果；第五版是唯一已通过 Smoke 的回退锚点。
3. **材料：**在 10 月 31 日 23:59 前于已有学术榜申请中核对并提交固定代码、实际配置、方法/来源、容量与限制、团队和公开展示字段，保存官网回执。初始申请审核通过和版本绑定都不能单独证明这些材料已提交。
4. **Full 自查：**官网八项须按实际证据核实后再勾选。模型规则项存在已记录的纯词法 Add 口径风险；用户已决定不发送询问信，不把未收到的答复写作合规证明。

首次 Full 应在材料与容量证据齐备、用户完成最终决策后尽早运行，为 11 月 4 日 23:59 停止时间预留 0.5–2 天和故障缓冲。Full 运行期间冻结部署、配置和卷操作；结束后按官网 30 天要求清理评测数据及派生副本。
