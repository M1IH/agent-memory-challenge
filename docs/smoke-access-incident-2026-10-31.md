# AML Smoke 访问故障摘要（2026-10-31）

供技术支持排查；不含评测 Key 或服务鉴权 Token。

- 账户：`eval_user_6af3bac5`，文本赛道，已绑定版本 `v1.5.2-compress-3d5f422`。
- 接口：`https://api-production-40d75.up.railway.app/add`、`https://api-production-40d75.up.railway.app/search`。
- 任务 `teval_27981a1477d5ca6c`：北京时间 09:05:33 首次尝试、09:41:19 同任务续跑，均为 `ADD_ACCESS_DENIED · HTTP 403`，0/1，无分数。
- 任务 `teval_32dc68b405e552f0`：在服务持续唤醒、`/health` 200 的条件下新建，仍为相同 403，无分数。
- Railway `production/api` 当前 deployment `4d5c34c8-2533-4612-9351-7e69eedcc348`，镜像 `sha256:e0fba106290992d5cc6b9cf69b3e4852d615d4be10a02cee2a025cfd9c66dfd0`；服务开启鉴权，应用无 403 返回路径，错误鉴权返回 401。
- Railway HTTP 日志在失败时段见 `/add`、`/search` 的 200 响应，HEAD 请求在唤醒时有 499、唤醒后有 405；未见 403。WAF Under Attack Mode 为 disabled。第十次提交前已确认服务在运行并返回 200。
- 此前相同账户已有八次成功的文本 Smoke；第九、十次是新绑定版本与当前部署镜像的评测。当前镜像的官方 Smoke 尚未通过，因此未启动 Full。

拟发送的技术问题：请检查这些任务的评测节点实际请求目标、收到的 403 响应来源及响应体、鉴权头是否被转发，以及是否有平台侧访问策略拦截。请告知是否可对相同任务续跑或在问题修复后重新运行 Smoke。
