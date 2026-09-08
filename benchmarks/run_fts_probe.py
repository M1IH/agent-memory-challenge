from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from pathlib import Path

from app.store import semantic_expansion_terms, tokenize
from benchmarks.evidence import validate_source_case


SUITE_FILES = {
    "hard": "hard_cases.json",
    "confirmation": "confirmation_cases.json",
    "holdout": "holdout_cases.json",
}


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def fts_expression(terms: list[str]) -> str:
    unique_terms = list(dict.fromkeys(term for term in terms if term))
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in unique_terms)


def probe_case(case: dict, candidate_limit: int) -> dict:
    validate_source_case(case)
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE candidates USING fts5(source_id UNINDEXED, terms)"
        )
        connection.executemany(
            "INSERT INTO candidates (source_id, terms) VALUES (?, ?)",
            [
                (memory["source_id"], " ".join(tokenize(memory["content"])))
                for memory in case["memories"]
            ],
        )
        terms = tokenize(case["query"])
        terms.extend(semantic_expansion_terms(case["query"]))
        for option in case.get("options", []):
            terms.extend(tokenize(option))
        expression = fts_expression(terms)
        rows = (
            connection.execute(
                """
                SELECT source_id FROM candidates
                WHERE candidates MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expression, candidate_limit),
            ).fetchall()
            if expression
            else []
        )
    finally:
        connection.close()

    candidate_ids = [row[0] for row in rows]
    expected = case["expected_source_ids"]
    covered = [source_id for source_id in expected if source_id in candidate_ids]
    return {
        "name": case["name"],
        "category": case["category"],
        "memory_count": len(case["memories"]),
        "candidate_count": len(candidate_ids),
        "candidate_ratio": len(candidate_ids) / len(case["memories"]),
        "expected_source_ids": expected,
        "covered_source_ids": covered,
        "missing_source_ids": [source_id for source_id in expected if source_id not in covered],
    }


def probe_suite(suite: str, candidate_limit: int) -> dict:
    path = Path(__file__).with_name(SUITE_FILES[suite])
    cases = json.loads(path.read_text(encoding="utf-8"))
    traces = [probe_case(case, candidate_limit) for case in cases]
    expected_count = sum(len(trace["expected_source_ids"]) for trace in traces)
    covered_count = sum(len(trace["covered_source_ids"]) for trace in traces)
    return {
        "suite": suite,
        "candidate_limit": candidate_limit,
        "cases": len(traces),
        "expected_evidence": expected_count,
        "covered_evidence": covered_count,
        "evidence_coverage": covered_count / expected_count,
        "mean_candidate_ratio": statistics.mean(
            trace["candidate_ratio"] for trace in traces
        ),
        "complete_cases": sum(not trace["missing_source_ids"] for trace in traces),
        "traces": traces,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure recall risk of direct SQLite FTS5 candidate filtering."
    )
    parser.add_argument(
        "--suite", choices=tuple(SUITE_FILES), action="append", dest="suites"
    )
    parser.add_argument("--candidate-limit", type=positive_int, default=1000)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    suites = args.suites or list(SUITE_FILES)
    reports = [probe_suite(suite, args.candidate_limit) for suite in suites]
    result = {"method": "direct_fts5_or_terms", "reports": reports}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_output:
        args.json_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
