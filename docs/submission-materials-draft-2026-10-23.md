# 第二期第四版保底提交材料草稿（2026-10-24）

这是供参赛者在官网逐项核对的草稿，**尚未提交**。材料截止为 **2026-10-31 23:59（北京时间）**，评测于 **2026-11-04 23:59（北京时间）**停止。以第四次 Smoke 已完成的 `v1.3.0-temporal-c0001f8` 为保底版本；若有通过全部门禁的新版，代码、镜像、容量与官网版本材料须整套重核。初始学术榜申请获批不等于第四版最终材料完整提交。填写前先读[提交就绪审计](submission-readiness-audit-2026-10-23.md)。身份证明、联系资料、Memory System Key 与其他凭证只能在官网指定安全字段由用户填写，不写入仓库或公开截图。

| 官网字段/材料 | 可直接使用的草稿或证据 | 提交前必须确认 |
| --- | --- | --- |
| 系统名称 | `Nagasaki soyo's memory`（用户提供的初始申请审核通过邮件） | 核对当前官网绑定名称；若变更，以官网现值为准。 |
| 类型与赛道 | Textual；初始审核邮件明确为学术榜，即当前官网所称开源方法榜 | 初始资格已通过；继续核对第四版材料和模型合规书面口径。 |
| 系统版本 | 第四次 Smoke 标签 `v1.3.0-temporal-c0001f8` | 核对官网版本 ID、Railway 当前部署及镜像 digest；最终候选若变化，所有材料同步。 |
| 公开仓库 | `https://github.com/M1IH/agent-memory-challenge` | 默认 `main` 仍显示第三版，不可仅给仓库根链接作为第四版证明。 |
| **第四版精确提交** | `https://github.com/M1IH/agent-memory-challenge/commit/c0001f84709ae134f3b5221574f3965f2f3f55c9` | 公开分支 `codex/task34-new-candidate` 可读；该 SHA 的 Actions run `39182694263` 成功，但不是当前生产身份的实时证明。 |
| HTTPS Endpoint | `https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`、`https://api-production-40d75.up.railway.app/health` | 10 月 24 日两次冷启动 `/health` 均为 200，约 7.67/8.16 秒；正式提交前核验带密钥读写、持久化及稳定性。 |
| 鉴权 | `Authorization: Bearer <Memory System Key>` | 真实 Key 仅通过官网指定字段传递，不复制到本草稿。 |
| 方法说明 | 见下方可粘贴正文。 | 最近记录的生产变量为 `AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`；提交前复核实际线上配置。 |
| 容量声明 | 单副本、挂载 `/data`；本机 Windows 词法同构测试：10,000 条记忆、8 用户、500 次 Add/96 次 Search，32 路 Search，Top-100，峰值 RSS 72,757,248 字节，96/96 检索正确。 | 这只是本机代理，**不能填写为 Railway 正式容量**。需取 Railway Free 当前额度、Linux 实际 RSS/CPU/卷、正式并发负载和部署身份后给出保守声明；见下方待填模板。 |
| 回退版本 | 第四版精确提交 `c0001f84709ae134f3b5221574f3965f2f3f55c9`；恢复 deployment 历史 ID `e42eb7f9-bf7f-4863-be1b-a425df6e7832`。 | 10 月 24 日 Railway 控制台仍显示该 deployment；OCI revision 与镜像 digest 未验。 |
| 联系方式、机构/团队、允许公开内容 | **由参赛者填写** | 不从本机资料猜测或自动提交。 |

## 可粘贴的方法说明

> 这是自托管的文本记忆检索服务，提供同步 Add 和 Search HTTPS API。Add 按 `user_id` 和 `session_id` 将消息写入 SQLite 持久库；Search 限定同一 `user_id`，用 BM25 风格词项评分、选择题选项通道、有限的词汇/实体关联，以及显式时间和状态信息对来源消息排序并返回证据。系统保留来源消息及时间信息，不在参赛服务中生成最终答案；评测平台的统一回答器负责作答。第四次 Smoke 对应的第四版代码提交为 `c0001f84709ae134f3b5221574f3965f2f3f55c9`。最近核对的生产变量为 `AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`，因此**已记录的生产运行是纯词法检索**，不调用参赛方 embedding 或 LLM。镜像构建仍包含本地 BGE 模型文件及可选向量检索代码；它们在上述配置下未启用。正式提交前将以 Railway 当前变量、OCI revision 和镜像 digest 再次确认运行配置。

若部署变量或镜像发生变化，须先修订这段说明并重新验证。镜像中的 BGE 能力不能被描述为当前线上能力。

## 可粘贴的原创工作与来源披露

> 本项目实现 FastAPI Add/Search 封装、SQLite 消息和请求账本、用户隔离、词项检索、有限关联、时间状态排序、测试与部署脚本，源码及改动见固定提交。方法参考了 [Agent Memory Leaderboard](https://github.com/AML-memory/agent-memory-leaderboard) 的 Add/Search 与统一回答器接口分工；[Graphiti](https://github.com/getzep/graphiti) 的来源、实体和时间有效性区分；[Mem0](https://github.com/mem0ai/mem0) 的原始记忆保留与检索关联；[HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) 的关联检索和模型身份绑定思路；以及 [LangMem](https://github.com/langchain-ai/langmem) 的记忆处理分层。本项目采用 SQLite 与有界规则实现，没有集成这些系统的图数据库、在线 LLM 抽取或后台整合组件。[设计来源复核](https://github.com/M1IH/agent-memory-challenge/blob/c0001f84709ae134f3b5221574f3965f2f3f55c9/docs/external-memory-systems-review.md)记载未复制上述第三方系统源码；参赛者提交前仍应复核此声明。项目代码按 MIT 许可公开。服务依赖 FastAPI、FastEmbed、Uvicorn 等第三方包，准确版本见[固定提交的依赖锁文件](https://github.com/M1IH/agent-memory-challenge/blob/c0001f84709ae134f3b5221574f3965f2f3f55c9/requirements.lock)；Docker 镜像包含经 FastEmbed 使用的 [Qdrant BGE Small EN v1.5 ONNX 量化模型固定 revision](https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/tree/52398278842ec682c6f32300af41344b1c0b0bb2)，其模型卡标注 Apache-2.0，上游 [BAAI 原模型](https://huggingface.co/BAAI/bge-small-en-v1.5)模型卡标注 MIT。已记录的生产配置关闭了 embedding；模型文件在镜像中但运行时未使用。上述许可标注来自模型卡，不能用项目 MIT 许可替代，也不等于镜像的第三方分发义务已验收。

上段按仓库现有实现和设计记录整理。若官网要求逐项列出论文作者、技术报告或代码改动，请从所链接的一手来源核对后补填；不能猜测作者或许可证。

**模型许可分发缺口（2026-10-25 只读核对）：**Dockerfile 锁定 Qdrant revision `52398278842ec682c6f32300af41344b1c0b0bb2`，其固定模型卡 YAML 为 `license: apache-2.0`，并注明它是 BAAI 模型的量化 ONNX 移植；BAAI 模型卡 API 标为 `mit`。当前 Dockerfile 的 `allow_patterns` 仅下载配置、tokenizer 和 ONNX 文件，没有下载模型卡或许可文本；仓库根 MIT `LICENSE` 仅覆盖本项目代码。最终提交前应核实模型分发所需的许可文本和署名如何随镜像/源码提供，并与第四版固定镜像身份一起处理；本稿只记录来源，不声称已完成法律合规审核。

## 容量栏：已知证据与待填模板

2026-10-23 Railway 页面曾显示单副本、挂载 `/data`、资源上限 1 vCPU / 0.5 GB RAM；2026-10-21 的轻量请求窗口内存峰值约 86 MB、卷约 65/500 MB，**不是正式并发负载**。2026-10-21 Windows 本机以生产同构纯词法配置做 10,000 条记忆、8 用户、500 次 Add（每次 20 条）、96 次 Search、32 路 Search、Top-100 合成测试，峰值 RSS 72,757,248 字节，96/96 Top-1 正确、零错误、零观察到的跨用户泄漏；Add/Search p95 约 0.13/0.91 秒。详见[Free 容量诊断](free-tier-capacity-2026-10-21.md)。**这些本机和轻量线上数据都不能写作 Railway 正式容量承诺。**

10 月 24 日公开长历史回放测得 SQLite 占用为原始输入文本的 **2.273–3.277 倍**（5,000 条）；扩大至 20,000 条后 LongMemEval/PersonaMem 为 2.888/3.440 倍，每条数据库增量基本稳定。官网披露文本评测近 300M tokens，但没有说明同一次 Full 有多少会写入 Add；在当前应用不清理旧实例的前提下，500 MB 卷存在条件性超额风险。[卷增长报告](railway-volume-growth-2026-10-24.md)仅用于容量规划，不能当作官方 Full 用量证明。

| 官网容量字段 | 提交前证据状态 |
| --- | --- |
| 当前 deployment ID、OCI revision、镜像 digest 与固定提交的对应 | **待实时核验**。历史标签 `restore c0001f8` 不足以证明当前镜像身份。 |
| Railway Free 当前余额、CPU/RAM/卷容量及使用量 | 10 月 24 日只读控制台：周期用量 `$0.85`、赠额 `$1.00`、单副本上限 1 vCPU/0.5 GB RAM、卷上限 500 MB。卷图表未给可读精确用量；`Estimated Bill $0.17` 与侧栏 `0 days or $1.00 left` 口径不一致，剩余运行时间不能确认。正式提交前必须重新核对。 |
| 按官方规模测得的 Add/Search 并发、Top-100、语料和用户数 | **未验收**。官方指南默认 Add 64、Search 32 并发；本机 8/32 合成测试不覆盖正式 Add 并发。 |
| Linux 容器 RSS/cgroup 峰值、CPU、卷增量、错误率、Add/Search p95 | **待最终镜像实测**，并记录测试日期与负载。 |
| 冷启动、持续可用性、重启后检索持久化 | `/health` 冷/热约 7.67/0.79 秒；最终镜像的读写、持续运行和重启恢复仍待复核。 |
| 向官网申报的 Add/Search 并发上限与运行限制 | **待填实测保守值**；不能直接照抄官方默认并发或本机代理结果。 |

取得实测后，容量说明可按以下格式填写。**含尖括号的占位文本不得提交：**

> 版本 `<官网版本 ID>` 对应公开提交 `<40 位 SHA>`、Railway deployment `<ID>`、OCI revision `<SHA>` 和镜像 digest `<digest>`。服务为单副本，SQLite 数据库位于持久卷 `/data`，实际资源为 `<CPU/RAM/卷>`。在 `<日期、最终镜像、语料规模、用户数、Add/Search 并发、Top-K>` 测试下，Add/Search 成功率为 `<值>`，p95 为 `<值>`，容器峰值内存 `<值>`、卷增量 `<值>`；已验证的重启恢复与冷启动边界为 `<值>`。据此申报 Add 并发上限 `<值>`、Search 并发上限 `<值>`，运行限制为 `<如有>`。

## 提交前四个停止点

1. **资格：**官网当前明确开源方法榜 embeddings 须 `text-embedding-v4`、LLM 相关组件须 `gpt-4o-mini`。当前纯词法线上配置及镜像内禁用 BGE 的审查口径待主办方书面确认。
2. **线上：**Railway Free 本周期已显示 `$0.85/$1.00` 用量，卷 500 MB；CLI 登录失效，尚无精确卷余量、正式并发容量与 OCI 镜像身份的实时证明。健康检查 200 不能替代带密钥读写、持久化和负载验收。本机 Docker Linux daemon 未就绪，启动服务需要系统权限；不能把 Windows 20k 写入回放当作正式 Linux 验收。
3. **材料：**初始学术榜申请审核已通过，四次 Smoke 也已成功；仍不能证明第四版完整材料已经更新并通过最终审查。需在已有 Key 下核对 `v1.3.0-temporal-c0001f8` 的版本 ID、赛道/组别、审核和绑定状态、固定提交、接口、容量、署名与允许公开字段，并保存脱敏回执；不要误申请新 Key。
4. **版本：**第五版尚无通过公开答案级净收益、跨能力回退、Free 正式容量与精确 SHA 门禁的候选。若最迟 10 月 27 日仍未全部通过，以第四版为材料基线；若换版，固定提交、CI、镜像、Railway deployment 和官网版本必须重新一致，并等新版本审核绑定。

## 截止倒排（北京时间）

| 时间 | 必须形成的产物或决策 |
| --- | --- |
| **10 月 24–25 日** | 只读核对官网第四版材料与绑定状态，取得模型规则书面口径；复核 Railway 当前部署、变量和 Free 余额。若规则要求改版，立即评估实现与审核时间。 |
| **10 月 26–27 日** | 对最终镜像补正式并发、持续运行、持久化及身份核验；冻结唯一候选。只有新版公开答案级净收益、回退、容量和精确 SHA 同时通过，才建议用户发起第五次 Smoke；否则保留第四版，不为等待满分延误材料。 |
| **10 月 28–29 日** | 将本稿所有“待核验”换成脱敏回执或实测值，核查第三方模型许可、来源署名、官网版本与线上镜像一致，形成可直接提交的材料包。 |
| **尽量在 10 月 30 日完成材料** | 保留提交回执和故障缓冲；**法定材料截止为 10 月 31 日 23:59**，不能把 11 月 4 日评测停止误当材料期限。 |
| **首次 Full 决策** | 模型合规、材料、版本身份、正式容量和官网八项自查均可核实后，另行取得用户明确授权。Full 通常约 0.5–2 天、最长 72 小时；第二次 Full 须首次完成 30 天后才能发起，本期应按一次正式机会倒排。运行期间冻结代码、镜像、配置与挂卷操作。 |

本倒排以 2026-10-23 官网规则核对为依据；正式操作前再查是否有新公告。评测任务结束后按规则在 30 天内删除评测数据及派生副本。

## 待向主办方确认的模型规则问题（草稿，尚未发送）

> 我参加第二期文本赛道开源方法榜（学术榜）。当前 Add/Search 系统采用纯词法检索，生产配置关闭 embedding，也不调用参赛方 LLM；Docker 镜像中包含但未启用本地 BGE 代码及模型文件。请确认：（1）在运行时完全不调用 embedding/LLM 的纯词法系统，是否满足本赛道 `text-embedding-v4` / `gpt-4o-mini` 模型规定？（2）镜像中保留但运行时禁用的 BGE 组件是否影响合规审查？如不符合，请明确必须修改的范围和提交截止前可采用的合规路径。谢谢。

用户于 2026-10-25 决定**暂不发送**此规则询问；本文件没有发送消息，也不填入联系人或凭证。模型合规风险保持未确认，不能把草稿或四次 Smoke 成功当作主办方书面认可。

## Full 按钮前的核对

官网显示的八项自我确认已逐条记录在[提交就绪审计](submission-readiness-audit-2026-10-23.md)。当前截图为 0/8 勾选；不得因为已有四次 Smoke 就自动勾选余项。尤其先补足模型规则口径、Railway 正式容量、最终部署版本与完整材料，再由参赛者核对真实性和反作弊声明。Full 仍需用户单独授权。
