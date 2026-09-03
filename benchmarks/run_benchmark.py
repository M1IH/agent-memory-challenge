from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from app.store import MemoryStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local retrieval benchmark.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print ranked candidates for cases with evidence outside rank one",
    )
    args = parser.parse_args()
    cases_path = Path(__file__).with_name("retrieval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    reciprocal_rank_sum = 0.0
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    evidence_count = 0
    category_scores: dict[str, list[float]] = defaultdict(list)

    with tempfile.TemporaryDirectory() as temp_dir:
        for case_index, case in enumerate(cases):
            store = MemoryStore(Path(temp_dir) / f"case-{case_index}.db")
            if case.get("single_add"):
                store.add(
                    request_id=f"case-{case_index}-session",
                    user_id="benchmark-user",
                    session_id="benchmark-session",
                    messages=[
                        {"role": memory.get("role", "user"), **memory}
                        for memory in case["memories"]
                    ],
                )
            else:
                for memory_index, memory in enumerate(case["memories"]):
                    store.add(
                        request_id=f"case-{case_index}-memory-{memory_index}",
                        user_id="benchmark-user",
                        session_id="benchmark-session",
                        messages=[{"role": memory.get("role", "user"), **memory}],
                    )
            results = store.search(
                user_id="benchmark-user",
                query=case["query"],
                options=case.get("options"),
                top_k=10,
            )
            expected_items = case.get("expected_all") or [case["expected"]]
            ranks = [
                next(
                    (
                        rank
                        for rank, result in enumerate(results, start=1)
                        if expected.lower() in result["content"].lower()
                    ),
                    None,
                )
                for expected in expected_items
            ]
            reciprocal_ranks = [0.0 if rank is None else 1.0 / rank for rank in ranks]
            reciprocal_rank_sum += sum(reciprocal_ranks)
            hits_at_1 += sum(rank == 1 for rank in ranks)
            hits_at_3 += sum(rank is not None and rank <= 3 for rank in ranks)
            hits_at_5 += sum(rank is not None and rank <= 5 for rank in ranks)
            evidence_count += len(ranks)
            case_score = sum(reciprocal_ranks) / len(reciprocal_ranks)
            category_scores[case["category"]].append(case_score)
            passed = all(rank is not None and rank <= 5 for rank in ranks)
            print(f"{'PASS' if passed else 'MISS'}  {case['name']}: ranks={ranks}")
            if args.verbose and any(rank != 1 for rank in ranks):
                for rank, result in enumerate(results, start=1):
                    content = result["content"].replace("\n", " | ")
                    print(f"      {rank:>2}. {result['score']:.6f}  {content}")

    print(f"\nEvidence Hit@1: {hits_at_1 / evidence_count:.3f} ({hits_at_1}/{evidence_count})")
    print(f"Evidence Hit@3: {hits_at_3 / evidence_count:.3f} ({hits_at_3}/{evidence_count})")
    print(f"Evidence Hit@5: {hits_at_5 / evidence_count:.3f} ({hits_at_5}/{evidence_count})")
    print(f"Evidence MRR:   {reciprocal_rank_sum / evidence_count:.3f}")
    print("Categories:")
    for category, scores in sorted(category_scores.items()):
        print(f"  {category}: {sum(scores) / len(scores):.3f}")


if __name__ == "__main__":
    main()
