# Iteration checkpoint

Resume from the highest unfinished priority in the competition plan. Each iteration ends with code review and relevant regression tests.

## Current review

- Fixed ablation subprocesses inheriting AML_EMBED_ENABLED=false and mislabeling lexical runs as hybrid/dense.
- Reject non-finite, negative, and zero RRF weights before search. Channel removal uses explicit switches.
- 42 unit tests pass locally, including concurrent writes across store instances and strict-source benchmark integration. This does not establish that the entire repository is bug-free.
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

## Evaluation limitations and next work

- The extended suite contains repeated templates and generally only 2-4 memories per query. Hit@5 saturation is not strong evidence of competitive recall.
- Cross-language examples cover one question template. Broader multilingual ability remains unverified.
- Initial high-distractor, source-ID baseline is now in place. Next: topic-scoped temporal boosts and entity-linked second-hop candidate retrieval; compare on fixed hard plus original extended suites, then add independent holdout cases before tuning fusion or diversity weights.
- Keep evaluation cases fixed when comparing retrieval changes; changing the suite means headline scores cannot be compared directly with prior runs.
- Review model identity compatibility, temporal boosts on unrelated updated facts, and deterministic tie-breaking in subsequent correctness passes. Legacy replay is now guarded, not automatically migrated.
- Local commit 137bda6 previously failed to push; verify current remote status before shipping accumulated fixes.
- Latest remote connectivity check also failed: ordinary `git ls-remote` could not connect; the sandbox-external retry was reset. Remote CI for accumulated changes remains unverified. Resume push/CI gate before claiming deployment readiness.
