"""Offline BEAM probe for a query-independent, dual-role compressed index.

Only the BEAM ``chat`` field builds the two indexes. The ordinary index keeps
the full original messages; a separate index stores bounded, extractive
excerpts grouped by conversation batch and role. A digest hit promotes its
original full messages into the returned Top-100 if an equal-character-budget
replacement exists. Gold source IDs and rubrics are read only after retrieval.

This is a source-message retrieval proxy, not answer or AML evaluation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path

from app.store import MemoryStore
from benchmarks.probe_beam_100k import (
    SOURCE_REVISION,
    SOURCE_SHA256,
    TARGET_CATEGORIES,
    flatten_source_ids,
    load_rows,
)


USER_CUES = re.compile(r"\b(?:i|my|we|our|want|need|plan|decid\w*|prefer\w*|chang\w*)\b", re.I)
ASSISTANT_CUES = re.compile(r"\b(?:recommend\w*|therefore|conclusion|summary|next|should|will|plan)\b", re.I)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
GROUP_SIZE = 4
EXCERPT_CHARS = 240
DIGEST_POOL = 30
PROMOTION_LIMIT = 32
CARD_LIMIT = 24
TIME_CARDS_PER_ROLE = 20
SUMMARY_INTENT = re.compile(
    r"\b(?:summar(?:y|ize|ise)|overview|overall|themes?|trajectory|"
    r"over time|throughout|evolv\w*|across (?:the|all|multiple) "
    r"(?:sessions|conversations))\b",
    re.I,
)


def excerpt(content: str, role: str, limit: int = EXCERPT_CHARS) -> str:
    """Select bounded original sentences using fixed, role-specific cues."""
    if limit < 20:
        raise ValueError("excerpt limit must be at least 20")
    sentences = [re.sub(r"\s+", " ", part).strip() for part in SENTENCE_BREAK.split(content)]
    sentences = [part for part in sentences if part]
    if not sentences:
        return ""
    cue = USER_CUES if role == "user" else ASSISTANT_CUES
    scored = sorted(
        range(len(sentences)),
        key=lambda index: (
            -(
                3 * bool(cue.search(sentences[index]))
                + 2 * bool(re.search(r"\d", sentences[index]))
                + int(index in (0, len(sentences) - 1))
            ),
            index,
        ),
    )
    chosen: list[int] = []
    used = 0
    for index in scored:
        remaining = limit - used - (2 if chosen else 0)
        if remaining < 20:
            break
        text = sentences[index]
        if len(text) > remaining:
            text = text[:remaining].rstrip()
        if not text:
            continue
        chosen.append(index)
        used += len(text) + (2 if len(chosen) > 1 else 0)
        if len(chosen) >= 2:
            break
    return " ".join(sentences[index][:limit] for index in sorted(chosen))[:limit]


def digest_groups(chat: list[list[dict]]) -> list[tuple[str, str, list[int]]]:
    """Make time-batch / role groups without consulting probe questions."""
    groups = []
    for batch_index, batch in enumerate(chat, 1):
        for role in ("user", "assistant"):
            messages = [message for message in batch if message["role"] == role]
            for offset in range(0, len(messages), GROUP_SIZE):
                members = messages[offset:offset + GROUP_SIZE]
                chunks = [
                    f"[{message['id']}] {excerpt(message['content'], role)}"
                    for message in members
                ]
                digest = f"batch {batch_index} {role} excerpts:\n" + "\n".join(chunks)
                groups.append((role, digest, [int(message["id"]) for message in members]))
    return groups


def promote_with_budget(
    baseline: list[dict], digest_sources: list[int],
    originals_by_source: dict[int, dict], source_by_id: dict[str, int],
    *, protected_prefix: int = 5, promotion_limit: int = PROMOTION_LIMIT,
) -> list[dict]:
    """Promote complete original messages without adding results or characters."""
    selected = list(baseline)
    original_count = len(selected)
    character_budget = sum(len(row["content"]) for row in baseline)
    insert_at = min(protected_prefix, original_count)
    promoted = 0
    protected_ids = {row["id"] for row in selected[:insert_at]}
    for source in digest_sources:
        if promoted >= promotion_limit:
            break
        original = originals_by_source.get(source)
        if original is None or original["id"] in protected_ids:
            continue
        current = next((i for i, row in enumerate(selected) if row["id"] == original["id"]), None)
        if current is not None:
            selected.pop(current)
            selected.insert(insert_at, original)
        else:
            # Prefer evicting a duplicated source; otherwise evict the lowest
            # ranked result that can pay for this source's full original text.
            counts = defaultdict(int)
            for row in selected:
                counts[source_by_id[row["id"]]] += 1
            eligible = [
                i for i in range(len(selected) - 1, insert_at - 1, -1)
                if selected[i]["id"] not in protected_ids
                and len(selected[i]["content"]) >= len(original["content"])
            ]
            if not eligible:
                continue
            evict = next(
                (i for i in eligible if counts[source_by_id[selected[i]["id"]]] > 1),
                eligible[0],
            )
            selected.pop(evict)
            selected.insert(insert_at, original)
        protected_ids.add(original["id"])
        insert_at += 1
        promoted += 1
    if len(selected) != original_count or sum(len(row["content"]) for row in selected) > character_budget:
        raise AssertionError("candidate exceeded baseline result count or character budget")
    if [row["id"] for row in selected[:protected_prefix]] != [row["id"] for row in baseline[:protected_prefix]]:
        raise AssertionError("candidate changed protected original prefix")
    return selected


def cards_with_budget(
    baseline: list[dict], digests: list[dict], card_sources: dict[str, list[int]],
    source_by_id: dict[str, int], *, protected_prefix: int = 5,
    card_limit: int = CARD_LIMIT,
) -> list[dict]:
    """Return short excerpt cards, retaining original Top-5 and total budget."""
    selected = list(baseline)
    character_budget = sum(len(row["content"]) for row in baseline)
    insert_at = min(protected_prefix, len(selected))
    represented = {source_by_id[row["id"]] for row in baseline}
    for digest in digests:
        if insert_at - protected_prefix >= card_limit:
            break
        card_id = f"card:{digest['id']}"
        sources = card_sources[digest["id"]]
        if set(sources) <= represented:
            continue
        card = {"id": card_id, "content": digest["content"]}
        eligible = [
            i for i in range(len(selected) - 1, insert_at - 1, -1)
            if len(selected[i]["content"]) >= len(card["content"])
        ]
        if not eligible:
            continue
        selected.pop(eligible[0])
        selected.insert(insert_at, card)
        represented.update(sources)
        insert_at += 1
    if len(selected) != len(baseline) or sum(len(row["content"]) for row in selected) > character_budget:
        raise AssertionError("card candidate exceeded baseline count or character budget")
    if [row["id"] for row in selected[:protected_prefix]] != [row["id"] for row in baseline[:protected_prefix]]:
        raise AssertionError("card candidate changed original Top-5")
    return selected


def evenly_spaced(items: list[dict], count: int) -> list[dict]:
    """Cover the full chronological index for one role without query tuning."""
    if len(items) <= count:
        return items
    if count < 2:
        raise ValueError("count must be at least two")
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def time_coverage_cards(all_digests: list[dict]) -> list[dict]:
    """Interleave uniform user and assistant excerpts across the timeline."""
    user = evenly_spaced([row for row in all_digests if row["role"] == "user"], TIME_CARDS_PER_ROLE)
    assistant = evenly_spaced([row for row in all_digests if row["role"] == "assistant"], TIME_CARDS_PER_ROLE)
    selected = user + assistant
    return sorted(selected, key=lambda row: (row["index"], row["role"]))


def score(
    required: set[int], results: list[dict], source_by_id: dict[str, int],
    card_sources: dict[str, list[int]] | None = None,
    original_contents: dict[int, str] | None = None,
    excerpts: dict[int, str] | None = None,
) -> dict:
    card_sources = card_sources or {}
    ranked = [source_by_id.get(row["id"]) for row in results]
    represented = [
        set(card_sources[row["id"]]) if row["id"] in card_sources
        else {source_by_id[row["id"]]}
        for row in results
    ]
    represented_union = set().union(*represented)
    full_union = set(ranked)
    partial_fraction = {}
    if original_contents is not None and excerpts is not None:
        for source in required:
            partial_fraction[str(source)] = (
                1.0 if source in full_union else
                round(len(excerpts.get(source, "")) / max(len(original_contents[source]), 1), 4)
                if source in represented_union else 0.0
            )
    return {
        "hit_at_5": bool(required.intersection(ranked[:5])),
        "complete_at_5": required <= set(ranked[:5]),
        "complete_at_100": required <= set(ranked[:100]),
        "represented_at_100": required <= represented_union,
        "represented_source_fraction": partial_fraction,
        "result_chars": sum(len(row["content"]) for row in results),
        "required_ranks": {
            str(source): ranked.index(source) + 1 if source in ranked else None
            for source in sorted(required)
        },
        "required_representation_ranks": {
            str(source): next((i + 1 for i, values in enumerate(represented) if source in values), None)
            for source in sorted(required)
        },
    }


def answer_evidence(
    results: list[dict], source_by_id: dict[str, int],
    card_sources: dict[str, list[int]] | None = None,
) -> list[dict]:
    """Save exact ordered Search content for a separately frozen answerer."""
    card_sources = card_sources or {}
    return [
        {
            "rank": rank,
            "kind": "card" if row["id"] in card_sources else "original",
            "source_id": source_by_id.get(row["id"]),
            "source_ids": card_sources[row["id"]] if row["id"] in card_sources else [source_by_id[row["id"]]],
            "content": row["content"],
            "chars": len(row["content"]),
        }
        for rank, row in enumerate(results, 1)
    ]


def run_conversation(store: MemoryStore, conversation: dict, *, candidate_mode: str = "full_promote") -> list[dict]:
    conversation_id = str(conversation["conversation_id"])
    original_user = f"beam-100k:{conversation_id}"
    digest_user = f"beam-digest:{conversation_id}"
    chat = conversation["chat"]
    original_contents = {int(message["id"]): message["content"] for batch in chat for message in batch}
    excerpts = {
        int(message["id"]): excerpt(message["content"], message["role"])
        for batch in chat for message in batch if message["role"] in ("user", "assistant")
    }
    original_ids = set()
    for batch_index, batch in enumerate(chat, 1):
        for message in batch:
            source = int(message["id"])
            if source in original_ids:
                raise ValueError(f"duplicate original source {conversation_id}:{source}")
            original_ids.add(source)
            content = message["content"]
            for chunk_index, start in enumerate(range(0, len(content), store.max_add_chars)):
                store.add(
                    request_id=f"chat:{source}:{chunk_index}", user_id=original_user,
                    session_id=f"batch:{batch_index}",
                    messages=[{"role": message["role"], "content": content[start:start + store.max_add_chars]}],
                )
    digest_sources = {}
    for index, (role, digest, sources) in enumerate(digest_groups(chat)):
        request_id = f"digest:{index}"
        store.add(
            request_id=request_id, user_id=digest_user,
            session_id=f"digest:{index}", messages=[{"role": role, "content": digest}],
        )
        digest_sources[request_id] = sources
    source_by_id = {}
    originals_by_source = {}
    digest_sources_by_id = {}
    all_digests = []
    with store._connection() as connection:
        for row in connection.execute(
            "SELECT id, request_id, role, content FROM memories WHERE user_id = ?",
            (original_user,),
        ):
            _, source_text, chunk_text = row["request_id"].split(":")
            source, chunk = int(source_text), int(chunk_text)
            source_by_id[row["id"]] = source
            if chunk == 0:
                originals_by_source[source] = {
                    "id": row["id"], "content": f"{row['role']}: {row['content']}",
                }
        for row in connection.execute(
            "SELECT id, request_id, role, content FROM memories WHERE user_id = ?", (digest_user,),
        ):
            digest_sources_by_id[row["id"]] = digest_sources[row["request_id"]]
            all_digests.append({
                "id": row["id"],
                "index": int(row["request_id"].split(":")[1]),
                "role": row["role"],
                "content": f"{row['role']}: {row['content']}",
            })
    all_digests.sort(key=lambda row: row["index"])
    if set(originals_by_source) != original_ids:
        raise ValueError("original message indexing incomplete")
    questions = ast.literal_eval(conversation["probing_questions"])
    rows = []
    for category in TARGET_CATEGORIES:
        for question_index, item in enumerate(questions[category][:2]):
            question = item["question"]
            baseline = store.search(user_id=original_user, query=question, options=None, top_k=100)
            digests = store.search(user_id=digest_user, query=question, options=None, top_k=DIGEST_POOL)
            source_order = [
                source for digest in digests
                for source in digest_sources_by_id[digest["id"]]
            ]
            summary_intent = bool(SUMMARY_INTENT.search(question))
            if candidate_mode == "time_coverage" and summary_intent:
                selected_digests = time_coverage_cards(all_digests)
                candidate = cards_with_budget(
                    baseline, selected_digests, digest_sources_by_id, source_by_id,
                    card_limit=TIME_CARDS_PER_ROLE * 2,
                )
                selected_card_sources = {
                    f"card:{digest['id']}": digest_sources_by_id[digest["id"]]
                    for digest in selected_digests
                }
            elif candidate_mode == "cards":
                candidate = cards_with_budget(baseline, digests, digest_sources_by_id, source_by_id)
                selected_card_sources = {
                    f"card:{digest['id']}": digest_sources_by_id[digest["id"]]
                    for digest in digests
                }
            else:
                candidate = (
                    list(baseline) if candidate_mode == "time_coverage" else
                    promote_with_budget(baseline, source_order, originals_by_source, source_by_id)
                )
                selected_card_sources = {}
            # Gold is accessed only after both Search calls and candidate selection.
            required = set(flatten_source_ids(item["source_chat_ids"]))
            if not required or not required <= original_ids:
                raise ValueError("invalid reference source IDs")
            rows.append({
                "conversation_id": conversation_id,
                "category": category,
                "question_index": question_index,
                "question": question,
                "summary_intent_triggered": summary_intent,
                "required_count": len(required),
                "baseline": score(required, baseline, source_by_id, original_contents=original_contents, excerpts=excerpts),
                "candidate": score(required, candidate, source_by_id, selected_card_sources, original_contents, excerpts),
                "baseline_results": answer_evidence(baseline, source_by_id),
                "candidate_results": answer_evidence(candidate, source_by_id, selected_card_sources),
                "candidate_promoted_sources": [
                    source_by_id[row["id"]] for row in candidate if row["id"] in source_by_id
                    if row["id"] not in {old["id"] for old in baseline}
                ],
                "candidate_card_sources": [
                    selected_card_sources[row["id"]] for row in candidate if row["id"] in selected_card_sources
                ],
            })
    return rows


def aggregate(rows: list[dict]) -> dict:
    result = {}
    for category in TARGET_CATEGORIES:
        cases = [row for row in rows if row["category"] == category]
        result[category] = {
            "cases": len(cases),
            "baseline_complete_at_100": sum(row["baseline"]["complete_at_100"] for row in cases),
            "candidate_complete_at_100": sum(row["candidate"]["complete_at_100"] for row in cases),
            "candidate_represented_at_100": sum(row["candidate"]["represented_at_100"] for row in cases),
            "summary_intent_triggered": sum(row["summary_intent_triggered"] for row in cases),
            "improved": sum(not row["baseline"]["complete_at_100"] and row["candidate"]["complete_at_100"] for row in cases),
            "regressed": sum(row["baseline"]["complete_at_100"] and not row["candidate"]["complete_at_100"] for row in cases),
            "baseline_median_chars": statistics.median(row["baseline"]["result_chars"] for row in cases),
            "candidate_median_chars": statistics.median(row["candidate"]["result_chars"] for row in cases),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/beam-100k.parquet"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-conversations", type=int, default=14)
    parser.add_argument("--candidate-mode", choices=("full_promote", "cards", "time_coverage"), default="full_promote")
    args = parser.parse_args()
    if args.development_conversations not in range(1, 15):
        parser.error("development-conversations must be 1..14")
    source_rows = load_rows(args.source)
    if len(source_rows) != 20:
        raise ValueError("expected exactly 20 BEAM 100K conversations")
    source_rows.sort(key=lambda row: int(row["conversation_id"]))
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "beam-dual-role.db", embedder=False)
        for conversation in source_rows[:args.development_conversations]:
            rows.extend(run_conversation(store, conversation, candidate_mode=args.candidate_mode))
    report = {
        "kind": "beam_100k_dual_role_compressed_index_proxy",
        "candidate_mode": args.candidate_mode,
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "store_sha256": hashlib.sha256(Path("app/store.py").read_bytes()).hexdigest(),
        "split": "conversation IDs 1..14 development; 15..20 untouched holdout",
        "development_conversations_run": args.development_conversations,
        "top_k": 100,
        "digest_pool": DIGEST_POOL,
        "promotion_limit": PROMOTION_LIMIT,
        "card_limit": CARD_LIMIT,
        "time_cards_per_role": TIME_CARDS_PER_ROLE,
        "case_count": len(rows),
        "aggregate": aggregate(rows),
        "rows": rows,
        "note": "complete_at_100 counts only full original messages; represented_at_100 also counts short excerpt cards and is not full evidence. Candidate Top-100 characters never exceed same-question baseline. Not answer accuracy or AML F1. Ordered evidence is saved for a separate answerer; rubric and ideal answer are absent.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "aggregate": report["aggregate"]}))


if __name__ == "__main__":
    main()
