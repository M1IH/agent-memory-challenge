from __future__ import annotations

import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.store import MemoryStore


ADD_REQUESTS = 48
MESSAGES_PER_REQUEST = 20
SEARCH_REQUESTS = 96


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return ordered[index]


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store = MemoryStore(Path(temp_dir) / "load-test.db")

        def add(request_index: int) -> float:
            started = time.perf_counter()
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
                    for message_index in range(MESSAGES_PER_REQUEST)
                ],
            )
            return time.perf_counter() - started

        add_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=64) as executor:
            add_latencies = list(executor.map(add, range(ADD_REQUESTS)))
        add_wall = time.perf_counter() - add_started

        def search(search_index: int) -> tuple[float, bool]:
            request_index = search_index % ADD_REQUESTS
            message_index = search_index % MESSAGES_PER_REQUEST
            expected = f"project-code-{request_index}-{message_index}"
            started = time.perf_counter()
            results = store.search(
                "load-user", f"Find project code {expected}", top_k=100
            )
            latency = time.perf_counter() - started
            return latency, bool(results and expected in results[0]["content"])

        search_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=32) as executor:
            search_results = list(executor.map(search, range(SEARCH_REQUESTS)))
        search_wall = time.perf_counter() - search_started
        search_latencies = [latency for latency, _ in search_results]
        correct = sum(is_correct for _, is_correct in search_results)

    print(
        f"Add: {ADD_REQUESTS} requests x {MESSAGES_PER_REQUEST} messages, "
        f"wall={add_wall:.2f}s, mean={statistics.mean(add_latencies):.2f}s, "
        f"p95={percentile(add_latencies, 0.95):.2f}s"
    )
    print(
        f"Search: {SEARCH_REQUESTS} requests / 32 workers, wall={search_wall:.2f}s, "
        f"mean={statistics.mean(search_latencies):.2f}s, "
        f"p95={percentile(search_latencies, 0.95):.2f}s"
    )
    print(f"Top-1 exact retrieval: {correct}/{SEARCH_REQUESTS}")


if __name__ == "__main__":
    main()
