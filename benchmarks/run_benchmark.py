from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig
from benchmarks.extended_cases import build_extended_cases


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local retrieval benchmark.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print ranked candidates for cases with evidence outside rank one",
    )
    parser.add_argument("--suite", choices=("core", "extended"), default="core")
    parser.add_argument("--fail-on-miss", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--top-k", type=positive_int, default=10)
    parser.add_argument("--disable-lexical", action="store_true")
    parser.add_argument("--disable-expansion", action="store_true")
    parser.add_argument("--disable-temporal", action="store_true")
    parser.add_argument("--lexical-weight", type=float, default=1.0)
    parser.add_argument("--dense-weight", type=float, default=0.85)
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args()
    cases_path = Path(__file__).with_name("retrieval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if args.suite == "extended":
        cases.extend(build_extended_cases())
    reciprocal_rank_sum = 0.0
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    evidence_count = 0
    category_scores: dict[str, list[float]] = defaultdict(list)

    with tempfile.TemporaryDirectory() as temp_dir:
        store = MemoryStore(
            Path(temp_dir) / "benchmark.db",
            embedder=False if args.no_embeddings else None,
            retrieval_config=RetrievalConfig(
                lexical_enabled=not args.disable_lexical,
                expansion_enabled=not args.disable_expansion,
                temporal_enabled=not args.disable_temporal,
                lexical_weight=args.lexical_weight,
                dense_weight=args.dense_weight,
            ),
        )
        for case_index, case in enumerate(cases):
            user_id = f"benchmark-user-{case_index}"
            if case.get("single_add"):
                store.add(
                    request_id=f"case-{case_index}-session",
                    user_id=user_id,
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
                        user_id=user_id,
                        session_id="benchmark-session",
                        messages=[{"role": memory.get("role", "user"), **memory}],
                    )
            results = store.search(
                user_id=user_id,
                query=case["query"],
                options=case.get("options"),
                top_k=args.top_k,
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
            if not args.quiet:
                print(f"{'PASS' if passed else 'MISS'}  {case['name']}: ranks={ranks}")
            if args.verbose and any(rank != 1 for rank in ranks):
                for rank, result in enumerate(results, start=1):
                    content = result["content"].replace("\n", " | ")
                    print(f"      {rank:>2}. {result['score']:.6f}  {content}")

    summary = {
        "suite": args.suite, "top_k": args.top_k, "cases": len(cases), "evidence": evidence_count,
        "hit_at_1": hits_at_1 / evidence_count, "hit_at_3": hits_at_3 / evidence_count,
        "hit_at_5": hits_at_5 / evidence_count, "mrr": reciprocal_rank_sum / evidence_count,
        "categories": {key: sum(values) / len(values) for key, values in sorted(category_scores.items())},
    }
    if not args.quiet:
        print(f"\nCases: {len(cases)}; evidence items: {evidence_count}")
        print(f"Evidence Hit@1: {summary['hit_at_1']:.3f} ({hits_at_1}/{evidence_count})")
        print(f"Evidence Hit@3: {hits_at_3 / evidence_count:.3f} ({hits_at_3}/{evidence_count})")
        print(f"Evidence Hit@5: {hits_at_5 / evidence_count:.3f} ({hits_at_5}/{evidence_count})")
        print(f"Evidence MRR:   {reciprocal_rank_sum / evidence_count:.3f}")
        print("Categories:")
        for category, scores in sorted(category_scores.items()):
            print(f"  {category}: {sum(scores) / len(scores):.3f}")
    if args.json_output:
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.fail_on_miss and hits_at_5 != evidence_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
