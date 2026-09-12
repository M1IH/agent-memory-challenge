from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tempfile
from collections import defaultdict
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig
from benchmarks.extended_cases import build_extended_cases
from benchmarks.evidence import complete_at, source_ranks, validate_source_case


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def evaluation_code_manifest(root: Path) -> dict[str, object]:
    relative_paths = (
        "app/store.py",
        "app/embedding.py",
        "benchmarks/run_benchmark.py",
        "benchmarks/evidence.py",
        "benchmarks/extended_cases.py",
    )
    files = {
        relative_path: hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
        for relative_path in relative_paths
    }
    combined = hashlib.sha256(
        b"\0".join(
            relative_path.encode() + b"\0" + files[relative_path].encode()
            for relative_path in relative_paths
        )
    ).hexdigest()
    return {"sha256": combined, "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local retrieval benchmark.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print ranked candidates for cases with evidence outside rank one",
    )
    parser.add_argument(
        "--suite",
        choices=("core", "extended", "hard", "confirmation", "holdout", "blind2"),
        default="core",
    )
    parser.add_argument("--fail-on-miss", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--top-k", type=positive_int, default=10)
    parser.add_argument("--disable-lexical", action="store_true")
    parser.add_argument("--disable-expansion", action="store_true")
    parser.add_argument("--disable-temporal", action="store_true")
    parser.add_argument("--disable-linkage", action="store_true")
    parser.add_argument("--lexical-weight", type=float, default=RetrievalConfig().lexical_weight)
    parser.add_argument("--dense-weight", type=float, default=RetrievalConfig().dense_weight)
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args()
    cases_path = Path(__file__).with_name("retrieval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if args.suite == "extended":
        cases.extend(build_extended_cases())
    elif args.suite in {"hard", "confirmation", "holdout", "blind2"}:
        filename = {
            "hard": "hard_cases.json",
            "confirmation": "confirmation_cases.json",
            "holdout": "holdout_cases.json",
            "blind2": "blind2_cases.json",
        }[args.suite]
        cases = json.loads(Path(__file__).with_name(filename).read_text(encoding="utf-8"))
        for case in cases:
            validate_source_case(case)
    reciprocal_rank_sum = 0.0
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    evidence_count = 0
    category_scores: dict[str, list[float]] = defaultdict(list)
    traces = []
    complete_counts = {1: 0, 3: 0, 5: 0, args.top_k: 0}
    config = RetrievalConfig(
        lexical_enabled=not args.disable_lexical,
        expansion_enabled=not args.disable_expansion,
        temporal_enabled=not args.disable_temporal,
        linkage_enabled=not args.disable_linkage,
        lexical_weight=args.lexical_weight,
        dense_weight=args.dense_weight,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        store = MemoryStore(
            Path(temp_dir) / "benchmark.db",
            embedder=False if args.no_embeddings else None,
            retrieval_config=config,
        )
        backend_name = None if store._embedder is None else os.getenv("AML_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        embedding_identity = (
            None if store._embedder is None
            else getattr(store._embedder, "index_identity", None)
        )
        for case_index, case in enumerate(cases):
            user_id = f"benchmark-user-{case_index}"
            source_by_request = {}
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
                    request_id = f"case-{case_index}-memory-{memory_index}"
                    if "source_id" in memory:
                        source_by_request[request_id] = memory["source_id"]
                    store.add(
                        request_id=request_id,
                        user_id=user_id,
                        session_id="benchmark-session",
                        messages=[{"role": memory.get("role", "user"), **{
                            key: value for key, value in memory.items() if key != "source_id"
                        }}],
                    )
            results = store.search(
                user_id=user_id,
                query=case["query"],
                options=case.get("options"),
                top_k=args.top_k,
            )
            source_by_id = {}
            if "expected_source_ids" in case:
                # Read identities from this isolated benchmark DB, not from
                # answer text or a duplicate of the production hashing code.
                with store._connection() as connection:
                    rows = connection.execute(
                        "SELECT id, request_id FROM memories WHERE user_id = ?", (user_id,)
                    ).fetchall()
                if len(rows) != len(source_by_request):
                    raise RuntimeError("source mapping count does not match inserted memories")
                source_by_id = {row["id"]: source_by_request[row["request_id"]] for row in rows}
                expected_items = case["expected_source_ids"]
                ranks = source_ranks(expected_items, results, source_by_id)
            else:
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
            for cutoff in complete_counts:
                complete_counts[cutoff] += complete_at(ranks, cutoff)
            traces.append({
                "name": case["name"], "category": case["category"],
                "candidate_count": len(case["memories"]), "expected": expected_items,
                "matching": "source_id" if source_by_id else "substring",
                "ranks": ranks, "complete_at_k": complete_at(ranks, args.top_k),
                "results": [{**result, "source_id": source_by_id.get(result["id"])} for result in results],
            })
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
        "complete_at_1": complete_counts[1] / len(cases),
        "complete_at_3": complete_counts[3] / len(cases),
        "complete_at_5": complete_counts[5] / len(cases),
        "complete_at_k": complete_counts[args.top_k] / len(cases),
        "evaluation_version": 3,
        "suite_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "retrieval_config": asdict(config), "embedding_model": backend_name,
        "embedding_identity": embedding_identity,
        "runtime": {
            "python": platform.python_version(),
            "numpy": version("numpy"), "fastembed": version("fastembed"),
            "max_context_chars": store._max_context_chars,
            "max_add_chars": store.max_add_chars,
            "max_search_chars": store.max_search_chars,
            "embedding_concurrency": (
                None if store._embedder is None else store._embedder.concurrency
            ),
            "embedding_batch_size": (
                None if store._embedder is None else store._embedder.batch_size
            ),
        },
        "evaluation_code": evaluation_code_manifest(Path(__file__).resolve().parents[1]),
        "case_traces": traces,
    }
    if not args.quiet:
        print(f"\nCases: {len(cases)}; evidence items: {evidence_count}")
        print(f"Evidence Hit@1: {summary['hit_at_1']:.3f} ({hits_at_1}/{evidence_count})")
        print(f"Evidence Hit@3: {hits_at_3 / evidence_count:.3f} ({hits_at_3}/{evidence_count})")
        print(f"Evidence Hit@5: {hits_at_5 / evidence_count:.3f} ({hits_at_5}/{evidence_count})")
        print(f"Evidence MRR:   {reciprocal_rank_sum / evidence_count:.3f}")
        print(f"All evidence retrieved @{args.top_k}: {summary['complete_at_k']:.3f}")
        print("Categories:")
        for category, scores in sorted(category_scores.items()):
            print(f"  {category}: {sum(scores) / len(scores):.3f}")
    if args.json_output:
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.fail_on_miss and hits_at_5 != evidence_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
