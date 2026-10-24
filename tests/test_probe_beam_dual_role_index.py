"""Invariants for the offline BEAM index comparison."""

from benchmarks.probe_beam_dual_role_index import (
    cards_with_budget,
    digest_groups,
    promote_with_budget,
    score,
)


def test_digest_groups_keep_roles_and_source_provenance_separate() -> None:
    chat = [[
        {"id": 1, "role": "user", "content": "I changed my plan to Paris."},
        {"id": 2, "role": "assistant", "content": "I recommend taking the train."},
        {"id": 3, "role": "user", "content": "My budget is 100 euros."},
    ]]
    groups = digest_groups(chat)
    assert [(role, sources) for role, _, sources in groups] == [
        ("user", [1, 3]), ("assistant", [2]),
    ]
    assert "Paris" in groups[0][1] and "train" not in groups[0][1]


def test_promoted_full_source_respects_count_char_budget_and_prefix() -> None:
    baseline = [
        {"id": name, "content": char * size}
        for name, char, size in (
            ("a", "a", 5), ("b", "b", 5), ("c", "c", 10),
            ("d", "d", 8), ("e", "e", 6), ("f", "f", 4),
        )
    ]
    source_by_id = {name: index for index, name in enumerate("abcdefx", 1)}
    candidate = promote_with_budget(
        baseline, [7], {7: {"id": "x", "content": "x" * 7}},
        source_by_id, protected_prefix=2,
    )
    assert [row["id"] for row in candidate[:3]] == ["a", "b", "x"]
    assert len(candidate) == len(baseline)
    assert sum(len(row["content"]) for row in candidate) <= sum(len(row["content"]) for row in baseline)
    assert promote_with_budget(
        baseline, [7], {7: {"id": "x", "content": "x" * 20}},
        source_by_id, protected_prefix=2,
    ) == baseline


def test_card_representation_is_not_counted_as_full_original_evidence() -> None:
    baseline = [
        {"id": str(index), "content": "x" * (20 + index)}
        for index in range(6)
    ]
    source_by_id = {str(index): index for index in range(6)}
    digests = [{"id": "digest", "content": "user: [9] changed plan"}]
    candidate = cards_with_budget(
        baseline, digests, {"digest": [9]}, source_by_id, protected_prefix=2,
    )
    assert [row["id"] for row in candidate[:2]] == ["0", "1"]
    assert len(candidate) == len(baseline)
    assert sum(len(row["content"]) for row in candidate) <= sum(len(row["content"]) for row in baseline)
    result = score(
        {9}, candidate, source_by_id, {"card:digest": [9]},
        original_contents={9: "changed plan and more detail"},
        excerpts={9: "changed plan"},
    )
    assert result["represented_at_100"]
    assert not result["complete_at_100"]
    assert 0 < result["represented_source_fraction"]["9"] < 1
