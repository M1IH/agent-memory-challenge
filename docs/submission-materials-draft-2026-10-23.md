# 第二期提交材料草稿（2026-10-23）

这是供参赛者在官网逐项核对的草稿，**尚未提交**。填写前先读[提交就绪审计](submission-readiness-audit-2026-10-23.md)。身份证明、联系资料、Memory System Key 与其他凭证只能在官网指定安全字段由用户填写，不写入仓库或公开截图。

| 官网字段/材料 | 可直接使用的草稿或证据 | 提交前必须确认 |
| --- | --- | --- |
| 系统名称 | `Nagasaki soyo's memory`（用户提供的初始申请审核通过邮件） | 核对当前官网绑定名称；若变更，以官网现值为准。 |
| 类型与赛道 | Textual；初始审核邮件明确为学术榜，即当前官网所称开源方法榜 | 初始资格已通过；继续核对第四版材料和模型合规书面口径。 |
| 系统版本 | 第四次 Smoke 标签 `v1.3.0-temporal-c0001f8` | 核对官网版本 ID、Railway 当前部署及镜像 digest；最终候选若变化，所有材料同步。 |
| 公开仓库 | `https://github.com/M1IH/agent-memory-challenge` | 默认 `main` 仍显示第三版，不可仅给仓库根链接作为第四版证明。 |
| 第四版精确提交 | `https://github.com/M1IH/agent-memory-challenge/commit/c0001f84709ae134f3b5221574f3965f2f3f55c9` | 公开可读；Actions run `39182694263` 成功，但不是当前生产身份的实时证明。 |
| HTTPS Endpoint | `https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`、`https://api-production-40d75.up.railway.app/health` | 10 月 23 日仅 `/health` 200 和无密钥 `/search` 401 已复核；正式提交前核验带密钥读写、持久化及稳定性。 |
| 鉴权 | `Authorization: Bearer <Memory System Key>` | 真实 Key 仅通过官网指定字段传递，不复制到本草稿。 |
| 方法说明 | 自托管 FastAPI Add/Search；SQLite 持久化与用户隔离；词项检索、候选关联、时间与状态治理；Search 按相关性返回证据，官方统一回答器负责最终作答。 | 对照**实际线上配置**复核：最近记录 `AML_EMBED_ENABLED=false`，不要宣称线上使用 BGE。补充原创范围、已借鉴工作与许可证引用。 |
| 容量声明 | 单副本、挂载 `/data`；本机 Windows 词法同构测试：10,000 条记忆、8 用户、500 次 Add/96 次 Search，32 路 Search，Top-100，峰值 RSS 72.8 MB，96/96 检索正确。 | 这只是本机代理，**不能填写为 Railway 正式容量**。需取 Railway Free 实际 RSS、卷、账单额度、冷启动、正式并发负载和部署身份后给出真实保守声明。 |
| 回退版本 | 第四版精确提交 `c0001f84709ae134f3b5221574f3965f2f3f55c9`；恢复 deployment 历史 ID `e42eb7f9-bf7f-4863-be1b-a425df6e7832`。 | 当前是否仍为该 deployment 待 Railway 实时确认。 |
| 联系方式、机构/团队、允许公开内容 | **由参赛者填写** | 不从本机资料猜测或自动提交。 |

## 提交前四个停止点

1. **资格：**官网当前明确开源方法榜 embeddings 须 `text-embedding-v4`、LLM 相关组件须 `gpt-4o-mini`。当前纯词法线上配置及镜像内禁用 BGE 的审查口径待主办方书面确认。
2. **线上：**Railway CLI 登录失效，尚无 Free 当前资源与精确部署身份的实时证明。
3. **材料：**初始学术榜申请审核已通过，四次 Smoke 也已成功；仍不能证明第四版完整材料已经更新并通过最终审查。需在已登录页面核对并保存脱敏回执。
4. **版本：**若第五版没有通过独立答案级、回退和容量门禁，材料应以已验证第四版为基线；若换版，固定提交、CI、镜像、Railway deployment 和官网版本必须重新一致。

官网材料截止 2026-10-31 23:59（UTC+8）；评测停止 2026-11-04 23:59。Full 需用户单独授权，并为约 0.5–2 天运行和故障预留时间。

## 待向主办方确认的模型规则问题（草稿，尚未发送）

> 我参加第二期文本赛道开源方法榜（学术榜）。当前 Add/Search 系统采用纯词法检索，生产配置关闭 embedding，也不调用参赛方 LLM；Docker 镜像中包含但未启用本地 BGE 代码及模型文件。请确认：（1）在运行时完全不调用 embedding/LLM 的纯词法系统，是否满足本赛道 `text-embedding-v4` / `gpt-4o-mini` 模型规定？（2）镜像中保留但运行时禁用的 BGE 组件是否影响合规审查？如不符合，请明确必须修改的范围和提交截止前可采用的合规路径。谢谢。

发送前须再次核对线上变量与镜像内容；由用户决定是否向主办方发送，不在此文档填入联系人或凭证。

## Full 按钮前的核对

官网显示的八项自我确认已逐条记录在[提交就绪审计](submission-readiness-audit-2026-10-23.md)。当前截图为 0/8 勾选；不得因为已有四次 Smoke 就自动勾选余项。尤其先补足模型规则口径、Railway 正式容量、最终部署版本与完整材料，再由参赛者核对真实性和反作弊声明。Full 仍需用户单独授权。
