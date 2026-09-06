# Iteration checkpoint

Resume from the highest unfinished priority in the competition plan. Each iteration ends with code review and relevant regression tests.

## Current review

- Fixed ablation subprocesses inheriting AML_EMBED_ENABLED=false and mislabeling lexical runs as hybrid/dense.
- Reject non-finite, negative, and zero RRF weights before search. Channel removal uses explicit switches.
- 50 unit tests pass locally, including concurrent writes across store instances and strict-source benchmark integration. This does not establish that the entire repository is bug-free.
- Reproduced and fixed ambiguous NUL-delimited memory IDs dropping another user's record. New IDs hash a JSON array; existing rows are not rewritten. Unexpected ID collisions now fail the transaction instead of silently discarding a row.
- Reproduced and fixed replay requiring a working encoder. Ledger preflight skips encoding for completed replays/conflicts; transactional claiming remains authoritative for concurrent writers.
- Reproduced and fixed connection leakage on PRAGMA failure.
- Only RequestConflictError maps to HTTP 409; unrelated backend ValueError remains an internal error without exposing its message to the client.
- Legacy requests without a payload ledger cannot be verified from contextual display text. Reuse returns an explicit conflict and rolls back the ledger claim, without changing old memories. Callers must use a new request ID if they intentionally want a new write.
- Reproduced and fixed `know` matching `now`: English temporal markers now require word boundaries.
- Reproduced and fixed insertion-dependent tied rankings. Lexical, dense, and fused channels use a final ID tie-break; BM25 accumulates sorted query terms to avoid hash-seed-dependent floating-point order.
- Original extended regression remains 125 cases / 169 evidence items, Hit@1 0.804734, Hit@5 1.0, MRR 0.891519 with the real model after these fixes.
- Local Uvicorn smoke passes health, authentication, synchronous Add and immediate Search with embeddings enabled. This is not Docker evidence.

## Strict-source diagnostic baseline (2026-09-05)

- Added separate `--suite hard`: 6 scenarios, 15 required evidence items, 12 distractors per scenario. Includes English and Chinese multi-hop, lists, and unrelated temporal updates. Do not mix its scores with the legacy substring-scored suites.
- Scoring resolves actual returned IDs to source IDs in the temporary benchmark DB. Source labels never enter memory content. All-required-evidence coverage and per-case ranked traces are recorded with suite/code hashes, configuration, and runtime versions.
- At top_k=5: hybrid retrieves 9/15 evidence items and completes 1/6 cases; lexical retrieves 12/15 and completes 3/6; hybrid without temporal weighting retrieves 10/15 and completes 2/6.
- Results: `benchmarks/hard-review.json`, `benchmarks/hard-lexical.json`, `benchmarks/hard-no-temporal.json`. These are small development diagnostics, not independent held-out evaluation or proof of competitive performance.
- The unrelated-update case moves from missing to rank 1 without temporal weighting. Fix topic relevance / entity linkage before changing global weights; old temporal-conflict cases benefit from the existing boost.

## Topic-scoped temporal iteration

- Root cause reproduced: unrelated `changed` records received +10 solely because the query asked for current information. Even a record with zero lexical overlap was returned.
- Temporal score boosts now require query-topic overlap, or a one-hop shared topical term with an explicitly relevant older timestamped record. English grammatical terms, Chinese temporal phrases and grammatical bigrams, and formatted timestamps are excluded from topic anchors.
- Shared-anchor lookup uses a term-to-earliest-timestamp index instead of pairwise memory comparisons. No new schema, model, external dependency, or global weight change.
- 46 local unit tests pass. New regressions cover unrelated updates, zero-overlap false recall, Chinese grammatical overlap, and same-topic updates without timestamps. Existing Room-101/Room-202 pronoun-update regression remains passing.
- Real-model extended regression (125 cases) passes the existing Hit@5 gate after the final changes.
- Fixed hard suite: unrelated updates now returns source `desk` at rank 1. Hybrid evidence Hit@5 improves from 9/15 to 10/15; complete cases from 1/6 to 2/6. Saved trace: `benchmarks/hard-temporal-scoped.json`.
- Limitations: topic overlap is a conservative heuristic, not entity resolution. Same-topic different-person facts can still be confused. English multi-hop and list misses remain. Next algorithm work is entity-linked candidate retrieval with separate holdout tests; keep these fixed suites for regression.
- Commit `e3e6ef4` was pushed and GitHub Actions run 33961161902 passed both unit/extended evaluation and Linux Docker offline Add/Search. Later commit `3bd5a2f` and the current fusion iteration still require push and exact-SHA CI.

## Remaining priorities

## List-completeness fusion iteration

- Root cause isolated by ablation: lexical hard retrieval returned all 15/15 required evidence items, while dense-heavy fusion displaced one required item from each list case at top_k=5.
- Fixed-suite weight sweep: lexical/dense 1.25/0.75 reached 14/15 and 5/6 complete; 1.5/0.5 and 2.0/0.5 both reached 15/15 and 6/6. Chose the smaller 1.5/0.5 lexical emphasis.
- On the pre-existing 125-case extended suite, 1.5/0.5 exactly preserves Hit@1 0.804734, Hit@3/5 1.0, MRR 0.891519, and every reported category score compared with the prior default.
- Default weights and benchmark CLI now share `RetrievalConfig` values to prevent configuration drift. Equal-RRF and explicit weight flags remain available for ablation.
- This is development-set evidence, not independent validation. Next evaluation task is a separately authored high-distractor confirmation set before further weight/reranking changes.

## One-hop entity linkage iteration

- Root cause reproduced: first-hop evidence entered lexical top-5, but a second-hop record with zero query overlap was filtered before it could become a candidate.
- Rejected a broad low-frequency-topic expansion after it polluted other entities and hurt the Chinese chain. Final implementation only bridges repeated Latin proper-name tokens from the top lexical seed and explicit identity/assignment seeds in the top five.
- Zero-overlap records remain excluded unless they share a bounded bridge entity. Seed evidence receives a small fixed bonus so multi-hop answers retain both ends of the chain. Generic `Room`, weekday names, and entities already present in the query are excluded.
- Linkage has an explicit `RetrievalConfig.linkage_enabled` switch and `--disable-linkage` ablation flag.
- 49 local unit tests pass after adding deterministic manager-to-schedule, project-to-room-key, and disabled-linkage regressions. Temporal ablation remains independent after excluding generic `Room` from entities.
- Fixed hard suite with real embeddings: evidence Hit@5 improves from 10/15 to 13/15, MRR from 0.408 to 0.521, and complete cases from 2/6 to 4/6. Both English multi-hop cases now retrieve all required source IDs. With linkage disabled, Hit@5 is 10/15 and complete cases are 2/6.
- Lexical hard diagnostic reaches 15/15 evidence and 6/6 complete cases, while hybrid remains 13/15 and 4/6 because dense fusion drops one item from each list case. Next priority is evidence-list completeness / diversity handling, measured against these fixed traces.
- Real-model extended regression remains Hit@5 1.0 and MRR 0.891519. These repeated-template cases are regression evidence, not an independent score.

- The extended suite contains repeated templates and generally only 2-4 memories per query. Hit@5 saturation is not strong evidence of competitive recall.
- Cross-language examples cover one question template. Broader multilingual ability remains unverified.
- Initial high-distractor, source-ID baseline is now in place. Next: topic-scoped temporal boosts and entity-linked second-hop candidate retrieval; compare on fixed hard plus original extended suites, then add independent holdout cases before tuning fusion or diversity weights.
- Keep evaluation cases fixed when comparing retrieval changes; changing the suite means headline scores cannot be compared directly with prior runs.
- Review model identity compatibility, temporal boosts on unrelated updated facts, and deterministic tie-breaking in subsequent correctness passes. Legacy replay is now guarded, not automatically migrated.
- Resume the push/CI gate for the latest local commit before claiming its deployment readiness; GitHub connectivity remains intermittent.
