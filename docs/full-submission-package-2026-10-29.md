# 首次 Full 提交材料包（2026-10-30，三版 Smoke 对照后）

> 第五版旧镜像 68.09 为最高分；第六版压缩 61.36，第七版同镜像关闭压缩 62.84，第八版从第五版精确源码重新构建镜像后 62.19。10 月 30 日 18:48 已重新部署压缩候选，新镜像尚无对应 Smoke。初始申请审核通过，官网参赛资料字段已填写；尚未发现独立的最终材料回执入口。不能把第五版旧镜像的 68.09 写成当前镜像的成绩。

## 已核实的可填信息

| 字段 | 目前准确值或说明 |
| --- | --- |
| 系统 | `Nagasaki soyo's memory`；文本赛道、学术榜，沿用已经通过五次 Smoke 的既有 Key |
| 已通过 Smoke 的版本 | `v1.4.0-stage-notice-5d1f82d`，任务 `teval_ba5f1ec7c158cd00`，2026-10-27 成功，平均 68.09 |
| 公开仓库 | `https://github.com/M1IH/agent-memory-challenge`；必须同时给精确提交，不能只填仓库根地址 |
| 已通过 Smoke 的精确源码 | `https://github.com/M1IH/agent-memory-challenge/commit/5d1f82d3d7789051b47c4a9f70f1dbf07d07c794` |
| 当前生产部署 | Railway `production/api`，从压缩提交 `3d5f42258365a57a1425ae64f01525a06429f26c` 重新构建的 deployment `afb585d2-3178-4252-a1e4-22f2d88bd949`，镜像 `sha256:e0fba106290992d5cc6b9cf69b3e4852d615d4be10a02cee2a025cfd9c66dfd0`；2026-10-30 18:48 CLI 显示 SUCCESS，`/health` 返回 200。此镜像尚未独立 Smoke |
| HTTPS 接口 | `https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`、`https://api-production-40d75.up.railway.app/health` |
| 鉴权 | `Authorization: Bearer <Memory System Key>`；Key 只能填官网指定安全字段，不写进公开材料 |
| 当前运行配置 | 纯词法、`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`、`AML_COMPRESS_TEXT=true`；新提交具备压缩编码及混合行解码路径 |
| 当前候选精确源码 | `https://github.com/M1IH/agent-memory-challenge/commit/5d1f82d3d7789051b47c4a9f70f1dbf07d07c794`；第五次原镜像 Smoke 68.09，新构建镜像第八次独立 Smoke 62.19，任务 `teval_55e300718ab6b533`、46/46 成功。压缩候选 `3d5f42258365a57a1425ae64f01525a06429f26c` 在第六、七次分别为 61.36、62.84 |
| 当前资源 | Railway Free，单副本，1 vCPU/0.5 GB RAM 上限，`/data` 卷 68.395008/500 MB（2026-10-30 CLI）；`/health` 返回 200。容量数字仍不能证明 Full 峰值安全 |

## 可粘贴的方法与来源说明

> 系统提供自托管的同步 Add/Search HTTPS API。Add 按 `user_id` 和 `session_id` 将原始对话及时间信息保存在 SQLite；Search 限定同一用户，结合 BM25 风格词项匹配、有限的实体关联、选择题选项、显式时间和当前状态信号，返回带来源的证据供平台统一回答器使用。当前生产关闭 embedding，参赛服务不调用回答 LLM。第五版增加对用户明确通知环境变化后证据的阶段优先排序；历史查询与没有该类通知的历史保持原排序。第五次文本 Smoke 取得 68.09。代码与依赖见上述精确提交。此为本项目实现；方法设计参考 AML Add/Search 协议及仓库 `docs/external-memory-systems-review.md` 中列出的 Graphiti、Mem0、HippoRAG、LangMem 等公开系统，不声称集成其源码。本项目代码以 MIT 许可公开；镜像含固定 BGE ONNX 文件但当前运行关闭该能力，第三方模型许可与来源应按仓库说明分别列示。

上段方法说明中的 68.09 和阶段优先排序属于第五版实测。第六、七版沿用检索排序，但官方 Smoke 分别为 61.36 和 62.84；在官网应按最终运行版本填写对应精确源码、配置和镜像 digest，不能沿用第五版版本名或分数。

## Full 前仍需取得的证据

1. **容量：**500 MB 卷能否承受本次 Full 的累计 Add、WAL 峰值和评测持续时间。当前没有官方单次 Full 的精确写入字节数；公开 100k 历史压缩后增量 161.26 MB 只是本地情景，不能据此确认整场可运行。Linux 1 vCPU/512 MiB、10k 长消息、16/16 并发测试已通过（[run 40818226083](https://github.com/M1IH/agent-memory-challenge/actions/runs/40818226083)）：Add/Search 零错误、96/96 Top-1、Search p95 12.60 秒、cgroup peak 105,177,088 B、OOM 0。线上 Add/Search 与同镜像重新部署后的持久化检索均通过。仍需官方 Smoke 实际卷增长和持续稳定性证据。
2. **版本：**第六、七、八版已分别绑定并通过 Smoke，分别为 61.36、62.84、62.19；第八版 A/B/C/D/E/G/H/I 为 80/100/55/53.33/100/30/50/54.17。提交 `3d5f42258365a57a1425ae64f01525a06429f26c` 的 CI 已通过，390/390 公开检索题的逐题来源排序和指标与未压缩版完全一致。第五版旧镜像已移除；当前虽恢复其精确源码，但新镜像得分较旧镜像低 5.90，不能把第五版得分套用于当前镜像。
3. **材料：**初始学术榜申请审核通过；官网参赛资料页当前已填写系统、团队、机构、成员和指导教师字段，并写明 11 月 4 日前核对。此前所称独立“最终材料回执”暂无可见入口证据，不再作为虚构门禁。10 月 31 日前仍须按赛事材料截止要求固定代码、实际配置、方法/来源、容量与限制，并保持本地与公开仓库内容一致。
4. **Full 自查：**官网八项须按实际证据核实后再勾选。模型规则项存在已记录的纯词法 Add 口径风险；用户已决定不发送询问信，不把未收到的答复写作合规证明。

首次 Full 应在材料与容量证据齐备、用户完成最终决策后尽早运行，为 11 月 4 日 23:59 停止时间预留 0.5–2 天和故障缓冲。Full 运行期间冻结部署、配置和卷操作；结束后按官网 30 天要求清理评测数据及派生副本。
