# External memory-system review

Checked 2026-09-06. This is a design comparison, not a claim that this entry reproduces
the cited systems or their published scores. No third-party source code was copied.

## Sources and useful patterns

- [Agent Memory Leaderboard](https://github.com/AML-memory/agent-memory-leaderboard):
  the open pipeline separates Add/Search from answer generation and judging. Its public
  prompts explicitly value recent supported facts and complete lists without extras.
  Our strict-source diagnostic therefore tracks all-required-evidence coverage, not only
  the first matching result.
- [Graphiti](https://github.com/getzep/graphiti): keeps source episodes, entities and
  temporal relationships distinct; facts have validity windows, and search combines
  semantic, keyword and graph traversal. We should borrow provenance and explicit
  supersession concepts, but not its graph-database/LLM extraction stack before latency,
  offline and deployment budgets justify it.
- [Mem0](https://github.com/mem0ai/mem0): its April 2026 README describes ADD-only
  accumulation plus entity linking for retrieval boosting. This supports retaining raw
  evidence and adding bounded links instead of overwriting source memories. Its managed
  benchmark numbers include proprietary optimizations and are not comparable to this entry.
- [HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG): uses graph association for
  multi-hop retrieval and binds persisted state to model, endpoint, normalization and
  component identity. The immediately applicable safeguard is refusing to mix embeddings
  created by different configurations, even when vector dimensions match.
- [LangMem](https://github.com/langchain-ai/langmem): separates hot-path memory tools
  from background extraction/consolidation. Background LLM consolidation is intentionally
  deferred here because the competition path needs deterministic synchronous Add and an
  offline Docker image first.

## Decision for this repository

1. Keep SQLite, BM25-like lexical retrieval, local embeddings and source memories. They
   already satisfy the small deployable/offline shape and have Linux Docker evidence.
2. Add an embedding identity manifest now. A same-dimension model change is silent data
   corruption at retrieval time, not merely a quality preference.
3. Keep entity linkage bounded and ablatable. Do not add Neo4j, an online LLM extractor,
   or unrestricted graph traversal until an independent confirmation set shows a need.
4. Next evaluate explicit provenance/supersession and larger candidate retrieval. Measure
   recall, latency and memory before adopting a graph backend.
