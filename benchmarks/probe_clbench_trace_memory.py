"""Replay public CLBench SQL explorations through AML Add/Search.

This is an offline retrieval proxy, not a CLBench run or answer score. SQL
queries and observations from earlier episodes enter Add; final ANSWER actions,
question labels, reference SQL, and benchmark answers never enter Add/Search.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from app.store import MemoryStore


TRACE_SHA256 = "36afab46d4969ece1853c3fc8701d4014bfcf6a6f491f7670a67aeb1c7382e2a"
NOTICE = (
    "NOTICE: The live database schema or contents may have changed since your "
    "earlier exploration. Inspect current metadata and data before relying on "
    "prior assumptions."
)
NOTICE_PREFIX = re.compile(r"^\s*(?:notice|important|update|system update|policy update)\s*:", re.I)
CHANGE_TERMS = re.compile(r"\b(?:changed|updated|migrated|replaced|no longer|new version)\b", re.I)
ENVIRONMENT_TERMS = re.compile(
    r"\b(?:schema|database|environment|rules|policy|configuration|api|tool|data|contents)\b", re.I
)


def is_environment_change_notice(role: str, content: str) -> bool:
    """Conservatively identify a short, explicit user-supplied version notice."""
    return (
        role == "user"
        and len(content) <= 500
        and NOTICE_PREFIX.search(content) is not None
        and CHANGE_TERMS.search(content) is not None
        and ENVIRONMENT_TERMS.search(content) is not None
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trace(path: Path, run_index: int) -> list[dict]:
    if _sha256(path) != TRACE_SHA256:
        raise ValueError("CLBench trace SHA-256 mismatch")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    runs = document["run_traces"]
    if run_index not in range(len(runs)):
        raise ValueError("run_index outside published trace set")
    trace = runs[run_index]["trace"]
    by_episode = defaultdict(list)
    for interaction in trace["interactions"]:
        by_episode[interaction["query"]["instance_index"]].append(interaction)
    if set(by_episode) != set(range(40)):
        raise ValueError("expected 40 sequential episodes")
    return [by_episode[index] for index in range(40)]


def _table_in_sql(sql: str, table: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(table) + r"(?![\w])", sql, re.I) is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trace", type=Path,
        default=Path("data/clbench-source/final_results/runs/mem0-gpt-5.4/tasks/database_exploration.json.gz"),
    )
    parser.add_argument("--run-index", type=int, default=0)
    parser.add_argument("--questions-root", type=Path, default=Path("data/clbench-source/data/database_exploration"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--persist-notice", action="store_true")
    parser.add_argument("--stage-cue", action="store_true")
    parser.add_argument("--prefer-current-stage", action="store_true")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("top-k must be positive")
    if args.prefer_current_stage and not args.persist_notice:
        parser.error("prefer-current-stage requires persist-notice")
    episodes = load_trace(args.trace, args.run_index)
    question_paths = [
        args.questions_root / "questions.json",
        args.questions_root / "questions_post_drift.json",
    ]
    questions = {}
    for path in question_paths:
        for item in json.loads(path.read_text(encoding="utf-8")):
            questions[item["question_id"]] = item
    all_tables = {
        table for question in questions.values()
        for table in question["tables_involved"]
    }
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "trace-memory.db", embedder=False)
        user_id = f"clbench-public-trace-run-{args.run_index}"
        source_by_memory = {}
        observations = {}
        current_epoch = 0
        detected_notices = 0
        for episode_index, interactions in enumerate(episodes):
            if episode_index == 20 and args.persist_notice:
                store.add(
                    request_id="stage-notice", user_id=user_id, session_id="notice",
                    messages=[{"role": "user", "content": NOTICE}],
                )
                if is_environment_change_notice("user", NOTICE):
                    current_epoch += 1
                    detected_notices += 1
            question_id = interactions[0]["query"]["metadata"]["question_id"]
            question = questions[question_id]
            query = question["question"]
            # The native task shows the notice once, at the transition.
            if episode_index == 20 or (args.stage_cue and episode_index >= 20):
                query = NOTICE + " " + query
            with store._connection() as connection:
                source_by_memory.update({
                    row["id"]: row["request_id"]
                    for row in connection.execute(
                        "SELECT id, request_id FROM memories WHERE user_id = ?", (user_id,)
                    )
                })
            results = store.search(
                user_id=user_id, query=query, options=None,
                top_k=max(args.top_k, 100) if args.prefer_current_stage else args.top_k,
            )
            if args.prefer_current_stage and current_epoch > 0:
                results.sort(key=lambda result: (
                    0 if source_by_memory[result["id"]] in observations
                    and observations[source_by_memory[result["id"]]][1] == current_epoch
                    else 1,
                ))
            results = results[:args.top_k]
            ranked = [source_by_memory[result["id"]] for result in results]
            stage = int(episode_index >= 20)
            required_tables = set(question["tables_involved"])
            eligible = {
                table for table in required_tables
                if any(
                    prior_stage == stage and _table_in_sql(sql, table)
                    for prior_stage, _epoch, sql in observations.values()
                )
            }
            covered = {
                table for table in eligible
                if any(
                    source in observations
                    and observations[source][0] == stage
                    and _table_in_sql(observations[source][2], table)
                    for source in ranked
                )
            }
            stale = sum(
                source in observations
                and observations[source][0] < stage
                and any(_table_in_sql(observations[source][2], table) for table in required_tables)
                for source in ranked
            )
            rows.append({
                "episode_index": episode_index,
                "question_id": question_id,
                "stage": stage,
                "eligible_table_count": len(eligible),
                "current_stage_table_recall": len(covered) / len(eligible) if eligible else None,
                "current_stage_tables_complete": covered == eligible if eligible else None,
                "stale_relevant_results": stale,
                "notice_retrieved": "stage-notice" in ranked,
                "ranked_observation_ids": ranked,
            })
            # Only observed exploration enters memory after the current query.
            for action_index, interaction in enumerate(interactions):
                action = interaction["response"]["action"]
                if action.get("action") != "QUERY":
                    continue
                sql = action["content"]
                observation = interaction["observation"]["content"]
                request_id = f"episode:{episode_index}:query:{action_index}"
                observations[request_id] = (stage, current_epoch, sql)
                store.add(
                    request_id=request_id, user_id=user_id,
                    session_id=f"episode:{episode_index}",
                    messages=[{
                        "role": "tool",
                        "content": f"SQL exploration: {sql}\nObservation: {observation}",
                    }],
                )
    groups = {
        str(stage): [row for row in rows if row["stage"] == stage]
        for stage in (0, 1)
    }
    aggregate = {}
    for stage, items in groups.items():
        eligible = [row for row in items if row["eligible_table_count"]]
        aggregate[stage] = {
            "episodes": len(items),
            "eligible_episodes": len(eligible),
            "complete_at_k": sum(row["current_stage_tables_complete"] for row in eligible),
            "mean_recall_at_k": (
                sum(row["current_stage_table_recall"] for row in eligible) / len(eligible)
                if eligible else None
            ),
            "episodes_with_stale_relevant_result": sum(row["stale_relevant_results"] > 0 for row in items),
            "notice_retrieved": sum(row["notice_retrieved"] for row in items),
        }
    report = {
        "kind": "clbench_public_sql_observation_retrieval_proxy",
        "trace_sha256": TRACE_SHA256,
        "question_file_sha256": {path.name: _sha256(path) for path in question_paths},
        "runner_sha256": _sha256(Path(__file__)),
        "store_sha256": _sha256(Path("app/store.py")),
        "run_index": args.run_index,
        "top_k": args.top_k,
        "persist_notice": args.persist_notice,
        "stage_cue": args.stage_cue,
        "prefer_current_stage": args.prefer_current_stage,
        "detected_notices": detected_notices,
        "table_vocabulary_size": len(all_tables),
        "aggregate": aggregate,
        "rows": rows,
        "note": "Offline table-observation retrieval; not CLBench reward, SQL answer correctness, or AML score.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["aggregate"]))


if __name__ == "__main__":
    main()
