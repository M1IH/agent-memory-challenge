"""Offline clause-balanced retrieval probe on public temporal development cases.

The reranker uses only the question and preexisting Top-100 Search results.
Reference answers and source IDs are consulted only after ranking for diagnostics.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from collections import Counter
from pathlib import Path

from app.store import MemoryStore, entity_terms, topic_terms
from benchmarks.public_eval_schema import load_suite


def event_clauses(question: str) -> list[str]:
    cleaned = question.strip().rstrip("?.")
    between = re.search(r"\bbetween\b", cleaned, re.I)
    if between:
        body = cleaned[between.end():].strip()
        parts = re.split(r"\s+and\s+", body, flags=re.I)
        if len(parts) >= 2:
            clauses = [" and ".join(parts[:-1]), parts[-1]]
            if all(len(topic_terms(clause)) >= 2 for clause in clauses):
                return clauses
    if re.search(r"\border\b", cleaned, re.I) and ":" in cleaned:
        parts = [re.sub(r"^and\s+", "", part.strip(), flags=re.I) for part in cleaned.split(":", 1)[1].split(",")]
        if len(parts) >= 2 and all(len(topic_terms(part)) >= 2 for part in parts):
            return parts
    return []


def clause_balanced(results: list[dict], question: str) -> list[dict]:
    clauses = event_clauses(question)
    if not clauses:
        return results
    result_terms = [topic_terms(result["content"]) for result in results]
    document_frequency = Counter(term for terms in result_terms for term in terms)
    selected: set[int] = set()
    for clause in clauses:
        terms = topic_terms(clause)
        named = entity_terms(clause)
        weights = {term: math.log((len(results) + 1) / (document_frequency[term] + 1)) for term in terms}
        denominator = sum(weights.values()) or 1.0
        available = [index for index in range(len(results)) if index not in selected]
        user_available = [
            index for index in available
            if re.match(r"^(?:\[[^]]+\] )?user:", results[index]["content"])
            and terms & result_terms[index]
        ]
        best = max(
            user_available or available,
            key=lambda index: (
                sum(weights[term] for term in terms & result_terms[index]) / denominator
                + 0.5 * len(named & entity_terms(results[index]["content"])) / max(len(named), 1),
                -index,
            ),
        )
        selected.add(best)
    ordered_indices = sorted(selected) + [index for index in range(len(results)) if index not in selected]
    return [results[index] for index in ordered_indices]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("data/longmemeval-s-normalized.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite = load_suite(args.suite)
    cases = [case for case in suite["cases"] if case["split"] == "development" and case["capabilities"][0] == "temporal-reasoning"]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "temporal-clause.db", embedder=False)
        for case in cases:
            user_id = "clause:" + case["case_id"]
            for index, memory in enumerate(case["memories"]):
                store.add(
                    request_id=f"{case['case_id']}:{index}", user_id=user_id,
                    session_id=memory["memory_id"],
                    messages=[
                        {"role": turn["role"], "content": turn["content"], "timestamp": memory["timestamp"]}
                        for turn in memory["turns"]
                    ],
                )
            results = store.search(user_id=user_id, query=case["question"], options=None, top_k=100)
            with store._connection() as connection:
                sources = {
                    row["id"]: row["session_id"]
                    for row in connection.execute("SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,))
                }
            candidate = clause_balanced(results, case["question"])
            required = set(case["evidence_memory_ids"])
            rows.append({
                "case_id": case["case_id"],
                "clause_count": len(event_clauses(case["question"])),
                "baseline_complete5": required <= {sources[result["id"]] for result in results[:5]},
                "candidate_complete5": required <= {sources[result["id"]] for result in candidate[:5]},
                "baseline_top5_sources": [sources[result["id"]] for result in results[:5]],
                "candidate_top5_sources": [sources[result["id"]] for result in candidate[:5]],
            })
    report = {"kind": "temporal_clause_retrieval_proxy", "case_count": len(rows), "rows": rows,
              "note": "Source-level proxy only; not final answer or official AML score."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    activated = [row for row in rows if row["clause_count"]]
    print(json.dumps({
        "cases": len(rows), "activated": len(activated),
        "baseline_complete5": sum(row["baseline_complete5"] for row in rows),
        "candidate_complete5": sum(row["candidate_complete5"] for row in rows),
        "activated_improve": sum(row["candidate_complete5"] and not row["baseline_complete5"] for row in activated),
        "activated_regress": sum(row["baseline_complete5"] and not row["candidate_complete5"] for row in activated),
    }))


if __name__ == "__main__":
    main()
