"""Retrieval-only proxy for reusable database knowledge in public CLBench questions.

Uses question text and public knowledge-dependency labels for scoring. SQL,
reference answers, and notes never enter Add or Search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from app.store import MemoryStore


CARDS = {
    "SCHEMA_MAP": "The product database has separate table families for office products, electronics, and musical instruments. Inspect each group's tables and columns before composing a query; the same concept may have a different column name by group.",
    "GROUP_ID": "Product group identity: office products use g1, electronics use g2, and musical instruments use g3. Match the natural-language product group to the corresponding table suffix.",
    "FK_JOINS": "To combine item catalog rows with reviews, ratings, or taxonomy, verify the group-specific foreign key and join on the shared product reference identifier ref_id. Count distinct products when joins multiply rows.",
    "DATA_QUALITY": "Product data can contain corrupted or far-future timestamps, missing prices, soft deletes, and stale fields. Check filters and data quality assumptions before aggregating.",
    "PRICE_FMT": "Price encodings differ by product group: some are dollars and others are cents. Convert units before comparing prices or averaging; a migration may leave old price columns stale.",
    "TS_FMT": "Review timestamps differ by group and migration stage: epoch milliseconds, epoch seconds, or ISO dates. Convert date boundaries to the matching stored unit before filtering.",
    "KV_ATTRS": "Product attributes may live in separate key-value tables for some groups and may be absent for others. Inspect attribute keys and join behavior before filtering by a product property.",
    "DOMAIN_JARGON": "Natural-language product category and review terms may differ from abbreviated database fields. Translate the question's domain term to the observed column or value before querying.",
    "CAT_LEVELS": "Taxonomy categories have hierarchy levels; the broadest category beneath the department is a different level from a narrow subcategory. Confirm cat_lvl before grouping category names.",
    "VRF_FMT": "Verified-purchase flags are encoded differently across product groups, including integer and text booleans. Inspect the stored representation before filtering verified reviews.",
    "COL_DIFF": "Product groups may have missing or extra columns and tables. Do not assume a column discovered in one group exists in the others.",
    "DRIFT": "After a database migration, old schema knowledge may be stale: prices, table names, timestamp fields, and soft-delete behavior can change. Reinspect affected columns and prefer current fields.",
}


def score_dependencies(required: list[str], ranked: list[str], k: int) -> dict:
    if not required or len(required) != len(set(required)):
        raise ValueError("dependencies must be nonempty and unique")
    if not set(required) <= CARDS.keys():
        raise ValueError("unknown knowledge dependency")
    found = set(required) & set(ranked[:k])
    return {"recall": len(found) / len(required), "complete": found == set(required)}


def question_query(case: dict, stage: str, stage_cue: bool) -> str:
    """Build a query from the question and optional public stage context only."""
    question = case["question"]
    if stage_cue and stage == "post_migration":
        return "After the database schema migration, use current fields. " + question
    return question


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("data/clbench-source"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--stage-cue", action="store_true", help="prepend public stage metadata to post-migration queries")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("top-k must be positive")
    files = {
        "pre_migration": args.source_root / "data/database_exploration/questions.json",
        "post_migration": args.source_root / "data/database_exploration/questions_post_drift.json",
    }
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "schema-proxy.db", embedder=False)
        user_id = "clbench-schema-proxy"
        for label, content in CARDS.items():
            store.add(
                request_id=f"card:{label}", user_id=user_id, session_id=label,
                messages=[{"role": "user", "content": content}],
            )
        with store._connection() as connection:
            source_by_id = {
                row["id"]: row["session_id"]
                for row in connection.execute("SELECT id, session_id FROM memories WHERE user_id = ?", (user_id,))
            }
        for stage, path in files.items():
            for case in json.loads(path.read_text(encoding="utf-8")):
                required = case["knowledge_dependencies"]
                query = question_query(case, stage, args.stage_cue)
                results = store.search(user_id=user_id, query=query, options=None, top_k=args.top_k)
                ranked = [source_by_id[result["id"]] for result in results]
                scored = score_dependencies(required, ranked, args.top_k)
                rows.append({
                    "stage": stage, "question_id": case["question_id"],
                    "required_count": len(required), "ranked_card_labels": ranked,
                    "recall_at_k": scored["recall"], "complete_at_k": scored["complete"],
                })
    report = {
        "kind": "clbench_database_schema_retrieval_proxy",
        "source_revision": "5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26",
        "source_file_sha256": {stage: hashlib.sha256(path.read_bytes()).hexdigest() for stage, path in files.items()},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "store_sha256": hashlib.sha256(Path("app/store.py").read_bytes()).hexdigest(),
        "card_count": len(CARDS), "top_k": args.top_k, "case_count": len(rows),
        "stage_cue": args.stage_cue,
        "mean_recall_at_k": sum(row["recall_at_k"] for row in rows) / len(rows),
        "complete_at_k": sum(row["complete_at_k"] for row in rows),
        "rows": rows,
        "note": "Hand-authored public README cards; retrieval-only proxy, not CLBench or AML score.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "mean_recall_at_k", "complete_at_k")}))


if __name__ == "__main__":
    main()
