"""Strict source scoring for diagnostic cases; never match answer substrings."""


def validate_source_case(case: dict) -> None:
    sources = [memory.get("source_id") for memory in case["memories"]]
    expected = case.get("expected_source_ids", [])
    if case.get("single_add"):
        raise ValueError("source cases require one message per add to avoid contextual copies")
    if not sources or any(not isinstance(source, str) or not source for source in sources):
        raise ValueError("every memory needs a nonempty source_id")
    if len(set(sources)) != len(sources):
        raise ValueError("duplicate source_id")
    if not expected or len(set(expected)) != len(expected) or not set(expected) <= set(sources):
        raise ValueError("expected_source_ids must be unique known sources")


def source_ranks(expected: list[str], results: list[dict], source_by_id: dict[str, str]) -> list[int | None]:
    ranks = {}
    for rank, result in enumerate(results, 1):
        # Unknown IDs are a harness/store contract error, not a retrieval miss.
        source = source_by_id[result["id"]]
        ranks.setdefault(source, rank)
    return [ranks.get(source) for source in expected]


def complete_at(ranks: list[int | None], cutoff: int) -> bool:
    return bool(ranks) and all(rank is not None and rank <= cutoff for rank in ranks)
