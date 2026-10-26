# 助手→用户上下文边界离线实验（2026-10-26）

## 结论

**淘汰，不修改生产 Add/Search，不建议发起第五次 Smoke。**第四版 Add 会把上一条消息拼入下一条消息的展示和索引文本；本实验仅在离线重放时把“assistant 后接 user”的 Add 分开，保留“user 后接 assistant”的上下文配对。目的是减少助手长回复或错误陈述附着到用户原话。没有使用参考答案决定分段。

在固定 LongMemEval-S development 来源顺序前 50 题、纯词法 Top-100 下，候选改变了 49/50 题的来源排序，但必要会话完整进入 Top-5 仍是 **41/50→41/50**，逐题 **0 改善、0 回退**；通勤时长题 `118b2229` 仍在 Top-5 外。前五道 `single-session-user` 题用同一固定本地 Qwen 4B、Top-5/8K 配对答题，严格匹配仍 **2/5→2/5**；通勤时长仍弃答，而原版事实正确的《The Glass Menagerie》变为弃答。因此来源代理无收益且答案有明确回退，不继续跑 390 题或其他能力，也不把严格分持平误认为安全。

## 复现与边界

离线实现位于 `benchmarks/add_context_modes.py`，调用现有 `MemoryStore.add`，只改变公开历史的请求分段。原消息、时间、会话 ID 与问题不变；生产代码和 Railway 均未改。命令：

```powershell
py -3.13 -m benchmarks.run_public_retrieval --limit 50 --top-k 100 --context-mode no_assistant_to_user --output data/longmemeval-no-assistant-user-dev50-2026-10-26.json
py -3.13 -m benchmarks.run_longmemeval_local_answerer --per-capability 5 --capability single-session-user --top-k 5 --context-mode no_assistant_to_user --skip-without --output data/longmemeval-no-assistant-user-answer5-2026-10-26.json
```

两份报告在 Git 忽略的 `data/`，SHA-256 分别为 `970e6776f3818427c8dbffbb817a03043a8fa290ceb8cdfc9ef4a32acd696278`、`731ddd3a38aab2fc9fdb478b39f1a06a98bc76739614c510767e94212bc82976`。复现脚本 `add_context_modes.py`、`run_public_retrieval.py`、`run_longmemeval_local_answerer.py` 的 SHA-256 分别为 `5f310b50d437682c2168d3ecfcd66f336aca15bd64719881f4656b42880ca991`、`980b22a9fda151960abf06c08faab1667c3f4ead4dd3fef6ab44a8b616d31e89`、`d15443a2bb0e9e48c40c46667fa06dbb9874c747ec621667aa0a40882ed337db`。已做 Python 编译检查。50 题来源覆盖与 5 题本地回答仅足以否决该候选，不能推断官方 AML 分数。
