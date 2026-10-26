"""Single fixed, answer-blind BEAM Top-300 diversification probe.

This is an offline source-coverage diagnostic, not a production Search change.
Gold source IDs are only inspected after selecting 100 messages.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pyarrow.parquet as pq

SOURCE = Path("data/beam-100k.parquet")
REPORT = Path("data/beam-100k-dev-14-top300.json")
SOURCE_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"
REPORT_SHA256 = "14108a009a8538596e941c9b546a906f25739c4918fd89eca4e049479c4a29eb"
TOKEN = re.compile(r"[a-z0-9]{3,}")
NOVELTY_WEIGHT = 0.25
PROTECTED_PREFIX = 5
RESULT_LIMIT = 100


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terms(content: str) -> set[str]:
    return set(TOKEN.findall(content.lower()))


def similarity(left: set[str], right: set[str]) -> float:
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def main() -> None:
    assert sha256(SOURCE) == SOURCE_SHA256
    assert sha256(REPORT) == REPORT_SHA256
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["top_k"] == 300 and report["case_count"] == 84
    history = {
        str(row["conversation_id"]): {
            int(message["id"]): message["content"]
            for batch in row["chat"] for message in batch
        }
        for row in pq.read_table(SOURCE).to_pylist()
    }
    aggregate: dict[str, dict[str, int]] = {}
    for row in report["rows"]:
        ranked = [int(value) for value in row["ranked_message_ids"]]
        assert 100 <= len(ranked) <= 300 and len(ranked) == len(set(ranked))
        content = history[row["conversation_id"]]
        token_sets = {message_id: terms(content[message_id]) for message_id in ranked}
        baseline = ranked[:RESULT_LIMIT]
        budget = sum(len(content[message_id]) for message_id in baseline)
        selected = ranked[:PROTECTED_PREFIX]
        selected_chars = sum(len(content[message_id]) for message_id in selected)
        remaining = set(ranked[PROTECTED_PREFIX:])
        rank = {message_id: index for index, message_id in enumerate(ranked)}
        max_similarity = {
            message_id: max(similarity(token_sets[message_id], token_sets[prior]) for prior in selected)
            for message_id in remaining
        }
        while len(selected) < RESULT_LIMIT:
            slots_after = RESULT_LIMIT - len(selected) - 1
            by_size = sorted(remaining, key=lambda message_id: (len(content[message_id]), rank[message_id]))
            smallest = sum(len(content[message_id]) for message_id in by_size[:slots_after])
            next_size = len(content[by_size[slots_after]]) if slots_after else 0
            small_members = set(by_size[:slots_after])
            viable = [
                message_id for message_id in remaining
                if selected_chars + len(content[message_id])
                + smallest - (len(content[message_id]) - next_size if message_id in small_members else 0) <= budget
            ]
            if not viable:
                raise AssertionError("cannot satisfy fixed character budget")
            candidate = max(
                viable,
                key=lambda message_id: (
                    1 / (1 + rank[message_id] / 20)
                    + NOVELTY_WEIGHT * (1 - max_similarity[message_id]),
                    -rank[message_id],
                ),
            )
            selected.append(candidate)
            selected_chars += len(content[candidate])
            remaining.remove(candidate)
            for message_id in remaining:
                max_similarity[message_id] = max(
                    max_similarity[message_id],
                    similarity(token_sets[message_id], token_sets[candidate]),
                )
        assert selected[:PROTECTED_PREFIX] == baseline[:PROTECTED_PREFIX]
        assert selected_chars <= budget
        required = {int(value) for value in row["required_ranks"]}
        bucket = aggregate.setdefault(row["category"], {
            "baseline_complete_100": 0, "candidate_complete_100": 0,
            "gain": 0, "loss": 0,
        })
        before = required <= set(baseline)
        after = required <= set(selected)
        bucket["baseline_complete_100"] += before
        bucket["candidate_complete_100"] += after
        bucket["gain"] += after and not before
        bucket["loss"] += before and not after
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
