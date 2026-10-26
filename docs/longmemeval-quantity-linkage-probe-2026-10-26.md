# 数量题实体关联消融（2026-10-26）

**结论：不改生产检索，不放行第五次 Smoke。**全局关闭实体关联虽使公开 LongMemEval-S development 的完整证据 Top-5 从 228/390 升到 243/390，但有 8 题回退。按问题字面 `how many|how much` 划出的 159 题中，关闭关联使 14 题来源覆盖改善、2 题回退；这一筛选仅依赖查询文本，不依赖参考答案。于是对来源顺序中首 30 道匹配题做了固定本地回答对照。

| 首 30 道数量题 | 第四版关联开启 | 关联关闭 |
| --- | ---: | ---: |
| 必要会话完整进入 Top-5 | 11/30 | 15/30 |
| Qwen 4B 严格答案匹配 | 4/30 | 3/30 |

来源改善的四题中，绘画估值和自行车支出仍弃答；衣物件数两版都答 2，参考为 3；影视观看时长由 2 周变 3 周，参考为 3.5 周。另有一题从 `20` 变为事实相同的 `You have 20 playlists on Spotify.`，导致严格分降低。其他答案也有变化，其中一题从弃答变为与参考相符的 `7 shirts`，但严格分仍因输出格式不匹配。整体不能证明答案级净提升，更不能把 Top-5 来源改善当作官方得分收益。

复现命令（固定本地 Ollama `qwen3-vl:4b-instruct`、Top-5、8K 上下文、temperature 0）：

```powershell
py -3.13 -m benchmarks.run_longmemeval_local_answerer --question-regex 'how (many|much)' --per-capability 30 --total-limit 30 --skip-without --output data/longmemeval-quantity-native-30-2026-10-26.json
py -3.13 -m benchmarks.run_longmemeval_local_answerer --question-regex 'how (many|much)' --per-capability 30 --total-limit 30 --skip-without --disable-linkage --output data/longmemeval-quantity-no-linkage-30-2026-10-26.json
```

两份逐题报告在 Git 忽略的 `data/` 中，SHA-256 分别为 `296fadab96fb6fce59dbf2eec3470e50ae2acebb85d8bd1ef356f0326428bb4a`、`bf12e00713d7d1c08ba088b1cd7b63849189bb780b716723841c17f185bb2376`。运行器 SHA-256 为 `1b79cc5d1f0db275206381207d452474a7c46814a5810baaf33a813086d7e2fc`；数据及模型身份写在报告中。运行器新增按查询正则和总题数固定选择公开 development 题的选项。`tests.test_longmemeval_local_answerer` 四项通过；未改 `app/` 或部署。

本地 4B 回答器不是官方 Answer/Judge，严格字面匹配也会低估事实等价回答。这组实验足以淘汰“按数量题关闭关联即可放行”的方案，不足以预测官方第五次 Smoke 分数。
