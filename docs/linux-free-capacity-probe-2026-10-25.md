# Railway Free 规格的 Linux 容器长消息压测（2026-10-25）

目的：在本机 Docker Linux 引擎未就绪时，用 GitHub Ubuntu runner 对当前词法路径施加 1 vCPU、512 MiB cgroup 限额。CI 只建临时镜像和临时 SQLite，不访问或部署 Railway，也不发起官方 Smoke/Full。工作流见 `.github/workflows/free-capacity-linux-probe.yml`。测试数据是每条追加 900 字符重复短语的**合成**历史，不代表官方 Full 语料或答案成绩。当前分支 `app/store.py` 含默认关闭的可选压缩开关；镜像与第四版线上部署不是同一 OCI digest。

共同负载：8 用户、500 次 Add × 20 条（共 10,000 条）、96 次 Top-100 Search；`AML_EMBED_ENABLED=false`、`AML_MEMORY_CACHE_USERS=1`、无压缩。记录进程 RSS、cgroup memory peak、OOM、完成时 DB+WAL+SHM、错误、Top-1 合成代码命中与 p95。15 秒 Search p95 是本地工程门槛，不是官网保证阈值。

| CI 运行与并发 Add/Search | Add/Search 错误 | Top-1 | Search p95 | cgroup 峰值 | OOM | 15 秒门槛 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| [40205570272](https://github.com/M1IH/agent-memory-challenge/actions/runs/40205570272)，64/32 | 0/0 | 96/96 | 14.654 s | 161,746,944 B | 无 | 通过，余量很小 |
| [40205861588](https://github.com/M1IH/agent-memory-challenge/actions/runs/40205861588)，64/32 重复 | 0/0 | 96/96 | **19.091 s** | 165,228,544 B | 无 | **失败** |
| [40206630605](https://github.com/M1IH/agent-memory-challenge/actions/runs/40206630605)，16/16 | 0/0 | 96/96 | 11.076 s | 161,693,696 B | 无 | 通过 |
| [40206801391](https://github.com/M1IH/agent-memory-challenge/actions/runs/40206801391)，16/16 重复 | 0/0 | 96/96 | 4.768 s | 169,291,776 B | 无 | 通过 |

64/32 使用公开提交 `6eda7f86cd4242ce5471df20ddb47697736cebb9`，16/16 使用远端提交 `f4b8999edd355bd6dfb5e1864a7226cad96cf093`；两者的应用代码相同，只变更 CI 并发参数。常规 GitHub `tests` 工作流在两个远端提交上均成功。16/16 两次镜像均带精确 revision 标签，但重建后的 image ID 分别为 `sha256:b8a01b740e92a3b86cc9a8d5d882bca97a85489a4bf0e7e59e1d471d2994fe11` 与 `sha256:5a845d4acbd25d7e0814ee2296c81e19906992ad28a21383c9b9a80959a2a63f`；不可把任何 CI 重建镜像冒充 Railway 正在运行的镜像。四次完成时数据库约 41.8 MB，远低于 500 MB，但这只覆盖 10,000 条合成消息，未覆盖 Full 累积写入。

官网公开评测表单的 Add 并发字段范围为 16–64、Search 并发为 16–256，二者默认 16。因此 **16/16 是可填写的下限**，在此合成负载上两次通过；64/32 一过一败，不能按该档申报已验证的稳定容量。即使选择 16/16，正式容量门禁仍缺真实 Full 写入量与 500 MB 卷峰值、Railway 当前额度/持续在线、线上最终镜像身份和重启恢复证据。不能从本 CI 结果推导第五次 Smoke 或首次 Full 已就绪。不得在未经实际申报核对前写成“已设置 16/16”。

原始 CI artifact 下载到被 Git 忽略的 `data/ci-free-capacity-*`；16/16 两次 `capacity-report.json` 的 SHA-256 分别为 `AD71B0EB0AA55D8117DD5E78D211A74E35789AC9E6FD7988C5C538AEE9AF75C2`、`A76BEB6E00246FF4D8771642E6F4E2E312B3AE83D312C5E359F49B4A6E32375C`。测试脚本只测合成代码检索，不证明公开答案级净收益。
