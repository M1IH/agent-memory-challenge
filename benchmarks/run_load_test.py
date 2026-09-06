from __future__ import annotations

import argparse
import json
import math
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.store import MemoryStore


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be between zero and one")
    ordered = sorted(values)
    index = max(math.ceil(len(ordered) * fraction) - 1, 0)
    return ordered[index]


def latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean_seconds": statistics.mean(values),
        "p50_seconds": percentile(values, 0.50),
        "p95_seconds": percentile(values, 0.95),
        "p99_seconds": percentile(values, 0.99),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a configurable local Add/Search load test.")
    parser.add_argument("--add-requests", type=positive_int, default=48)
    parser.add_argument("--messages-per-request", type=positive_int, default=20)
    parser.add_argument("--search-requests", type=positive_int, default=96)
    parser.add_argument("--add-workers", type=positive_int, default=64)
    parser.add_argument("--search-workers", type=positive_int, default=32)
    parser.add_argument("--top-k", type=positive_int, default=100)
    parser.add_argument("--no-embeddings", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        store = MemoryStore(
            Path(temp_dir) / "load-test.db",
            embedder=False if args.no_embeddings else None,
        )

        def add(request_index: int) -> tuple[float, str | None]:
            started = time.perf_counter()
            try:
                store.add(
                    request_id=f"load-request-{request_index}",
                    user_id="load-user",
                    session_id=f"load-session-{request_index}",
                    messages=[
                        {
                            "role": "user" if message_index % 2 == 0 else "assistant",
                            "timestamp": 1704067200000 + request_index * 100000 + message_index,
                            "content": (
                                f"Project code project-code-{request_index}-{message_index} "
                                f"belongs to test record {request_index}."
                            ),
                        }
                        for message_index in range(args.messages_per_request)
                    ],
                )
            except Exception as exc:
                return time.perf_counter() - started, type(exc).__name__
            return time.perf_counter() - started, None

        add_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.add_workers) as executor:
            add_results = list(executor.map(add, range(args.add_requests)))
        add_wall = time.perf_counter() - add_started
        add_latencies = [latency for latency, _ in add_results]
        add_errors = [error for _, error in add_results if error is not None]
        successful_messages = (
            args.add_requests - len(add_errors)
        ) * args.messages_per_request

        def search(search_index: int) -> tuple[float, bool, str | None]:
            request_index = search_index % args.add_requests
            message_index = search_index % args.messages_per_request
            expected = f"project-code-{request_index}-{message_index}"
            started = time.perf_counter()
            try:
                results = store.search(
                    "load-user", f"Find project code {expected}", top_k=args.top_k
                )
            except Exception as exc:
                return time.perf_counter() - started, False, type(exc).__name__
            latency = time.perf_counter() - started
            return latency, bool(results and expected in results[0]["content"]), None

        search_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.search_workers) as executor:
            search_results = list(executor.map(search, range(args.search_requests)))
        search_wall = time.perf_counter() - search_started
        search_latencies = [latency for latency, _, _ in search_results]
        search_errors = [error for _, _, error in search_results if error is not None]
        correct = sum(is_correct for _, is_correct, _ in search_results)

    memory_count = args.add_requests * args.messages_per_request
    report = {
        "config": {
            "add_requests": args.add_requests,
            "messages_per_request": args.messages_per_request,
            "memory_count": memory_count,
            "search_requests": args.search_requests,
            "add_workers": args.add_workers,
            "search_workers": args.search_workers,
            "top_k": args.top_k,
            "embeddings_enabled": not args.no_embeddings,
            "percentile_method": "nearest-rank",
        },
        "add": {
            "wall_seconds": add_wall,
            "successful_messages": successful_messages,
            "throughput_messages_per_second": successful_messages / add_wall,
            "errors": len(add_errors),
            "error_types": sorted(set(add_errors)),
            **latency_summary(add_latencies),
        },
        "search": {
            "wall_seconds": search_wall,
            "throughput_requests_per_second": args.search_requests / search_wall,
            "errors": len(search_errors),
            "error_types": sorted(set(search_errors)),
            "top_1_correct": correct,
            "top_1_accuracy": correct / args.search_requests,
            **latency_summary(search_latencies),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json_output:
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if add_errors or search_errors or correct != args.search_requests:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
