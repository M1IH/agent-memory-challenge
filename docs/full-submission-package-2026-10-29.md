# 首次 Full 提交材料包（2026-10-29，待最终版本固定）

## 已核实的可填信息

| 字段 | 目前准确值或说明 |
| --- | --- |
| 系统 | `Nagasaki soyo's memory`；文本赛道、学术榜，沿用已经通过五次 Smoke 的既有 Key |
| 已通过 Smoke 的版本 | `v1.4.0-stage-notice-5d1f82d`，任务 `teval_ba5f1ec7c158cd00`，2026-10-27 成功，平均 68.09 |
| 公开仓库 | `https://github.com/M1IH/agent-memory-challenge`；必须同时给精确提交，不能只填仓库根地址 |
| 已通过 Smoke 的精确源码 | `https://github.com/M1IH/agent-memory-challenge/commit/5d1f82d3d7789051b47c4a9f70f1dbf07d07c794` |
| 生产部署 | Railway `production/api`，deployment `daa06888-0fc1-480c-8184-6e80530eea48`，镜像 `sha256:56db0bdc829b4757c5af37f5903848f6cc0730cb7f08cf9fcd4ae67219417800`；2026-10-29 CLI 显示 SUCCESS |
| HTTPS 接口 | `https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`、`https://api-production-40d75.up.railway.app/health` |
| 鉴权 | `Authorization: Bearer <Memory System Key>`；Key 只能填官网指定安全字段，不写进公开材料 |
| 当前运行配置 | 已记录的生产配置为纯词法、`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`；压缩升级候选未部署 |
| 当前资源 | Railway Free，单副本，1 vCPU/0.5 GB RAM 上限，`/data` 卷 66.363392/500 MB（2026-10-29 CLI）；当前账期用量约 `$0.00585`，月末 11 月 20 日；本次 `/health` 冷唤醒 200，9.56 秒 |

## 可粘贴的方法与来源说明

> 系统提供自托管的同步 Add/Search HTTPS API。Add 按 `user_id` 和 `session_id` 将原始对话及时间信息保存在 SQLite；Search 限定同一用户，结合 BM25 风格词项匹配、有限的实体关联、选择题选项、显式时间和当前状态信号，返回带来源的证据供平台统一回答器使用。当前生产关闭 embedding，参赛服务不调用回答 LLM。第五版增加对用户明确通知环境变化后证据的阶段优先排序；历史查询与没有该类通知的历史保持原排序。第五次文本 Smoke 取得 68.09。代码与依赖见上述精确提交。此为本项目实现；方法设计参考 AML Add/Search 协议及仓库 `docs/external-memory-systems-review.md` 中列出的 Graphiti、Mem0、HippoRAG、LangMem 等公开系统，不声称集成其源码。本项目代码以 MIT 许可公开；镜像含固定 BGE ONNX 文件但当前运行关闭该能力，第三方模型许可与来源应按仓库说明分别列示。

若最终采用压缩升级，必须把上段的代码链接、版本名、部署 ID 和镜像 digest 全部换成新版本实际值，并补充一句“新写入的 SQLite 文本和词项以 zlib 压缩保存，旧行仍可读”。不能把本地候选写成已通过 Smoke 的线上版本。

## Full 前仍需取得的证据

1. **容量：**500 MB 卷能否承受本次 Full 的累计 Add、WAL 峰值和评测持续时间。当前没有官方单次 Full 的精确写入字节数；公开 100k 历史压缩后增量 161.26 MB 只是本地情景，不能据此确认整场可运行。最终候选需 Linux 1 vCPU/512 MiB 16/16、线上持久化和监控证据。
2. **版本：**若发布压缩候选，在官网新增独立版本、运行该版本的 Smoke，并核实精确源码 SHA、CI、OCI revision、Railway digest 与绑定端点。未完成时第五版是唯一已通过 Smoke 的回退锚点。
3. **材料：**在 10 月 31 日 23:59 前于已有学术榜申请中核对并提交固定代码、实际配置、方法/来源、容量与限制、团队和公开展示字段，保存官网回执。初始申请审核通过和版本绑定都不能单独证明这些材料已提交。
4. **Full 自查：**官网八项须按实际证据核实后再勾选。模型规则项存在已记录的纯词法 Add 口径风险；用户已决定不发送询问信，不把未收到的答复写作合规证明。

首次 Full 应在材料与容量证据齐备、用户完成最终决策后尽早运行，为 11 月 4 日 23:59 停止时间预留 0.5–2 天和故障缓冲。Full 运行期间冻结部署、配置和卷操作；结束后按官网 30 天要求清理评测数据及派生副本。
